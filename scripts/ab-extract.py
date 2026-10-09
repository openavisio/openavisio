#!/usr/bin/env python3
"""A/B-compare extraction models on real documents via the aiservice.

For each document: get the text once (shared), then run /extract-entities with
every given model and write the JSONs next to each other for diffing.
Deterministic since aiservice runs temperature=0, so differences are model
differences.

Two ways to supply documents. Both are read-only — nothing is ever written back
into a patient record.

**From files**, OCR'd here:

    python3 scripts/ab-extract.py --url http://localhost:8000 \
        --models qwen3.6:27b-mtp-q4_K_M other:model --language de doc1.pdf doc2.pdf

**From a deployment's own documents** (`--from-db`), reusing the OCR the
pipeline already ran, so no storage file is touched and nothing is re-OCR'd:

    python3 scripts/ab-extract.py --from-db --limit 12 \
        --models qwen3.6:27b-mtp-q4_K_M other:model

`extracted_text` is encrypted under the patient's KEK (ADR 031), so this shells
out to `docker compose exec backend` and decrypts through the app's own code —
run it in the deployment directory on the host. Set AISERVICE_TOKEN if the
deployment sets one. Inside the compose network the aiservice listens on
http://aiservice:8000.

Results land in ./ab-results/<document>/<model>.json plus a summary table.
"""
import argparse
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _auth_headers() -> dict:
    """The aiservice gates everything but /health when AISERVICE_TOKEN is set."""
    token = os.environ.get("AISERVICE_TOKEN", "").strip()
    return {"X-AI-Service-Token": token} if token else {}


def post_json(url: str, payload: dict, timeout: int = 600, retries: int = 5) -> dict:
    """POST, backing off on rate limits.

    Hosted providers cap requests and tokens per minute, and the aiservice
    reports a 429 as a normal result with an `error` field. Without this, a
    throttled document is indistinguishable from a model that failed to
    extract anything — which is exactly how it was misread once.
    """
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json", **_auth_headers()},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == retries - 1:
                raise
            result = {"error": "429"}
        if "429" not in str(result.get("error") or "") or attempt == retries - 1:
            return result
        wait = 15 * (attempt + 1)
        print(f" rate limited, {wait}s …", end="", flush=True)
        time.sleep(wait)
    return result


def post_file(url: str, path: Path, timeout: int = 600) -> dict:
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: {ctype}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **_auth_headers()},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# Runs inside the backend container, which is the only place that has both the
# app's crypto and the per-patient KEKs. Reading `document_references` directly
# yields ciphertext: `extracted_text` is encrypted under the patient's KEK
# (ADR 031, `pipeline.py`), the plaintext column that ADR 022 describes is gone.
_FETCH = r"""
import asyncio, json, sys
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.encryption import decrypt_str
from app.core.patient_keys import get_patient_kek
from app.models.document import DocumentReference

async def main(limit):
    out = []
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(DocumentReference)
            .where(DocumentReference.extracted_text.is_not(None),
                   DocumentReference.is_deleted == False)  # noqa: E712
        )).scalars().all()
        keks = {}
        for d in rows:
            if d.patient_id not in keks:
                keks[d.patient_id] = await get_patient_kek(db, d.patient_id)
            try:
                text = decrypt_str(d.extracted_text, keks[d.patient_id])
            except Exception as exc:               # a KEK we cannot open is not fatal here
                print(f"skip {d.id}: {exc}", file=sys.stderr)
                continue
            out.append({"id": str(d.id), "name": d.file_name or str(d.id), "text": text})
    out.sort(key=lambda r: len(r["text"]), reverse=True)
    print(json.dumps(out[:limit]))

asyncio.run(main(int(sys.argv[1])))
"""


def docs_from_db(compose_dir: Path, limit: int) -> list[tuple[str, str]]:
    """(name, text) for documents whose OCR already ran. Read-only.

    Decryption happens inside the backend container through the app's own code
    path, so nothing here reimplements the crypto and no key leaves the box.

    Longest first: a model that truncates, or one that spends its context
    thinking, shows it on the long documents and nowhere else.
    """
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend",
         "/app/.venv/bin/python", "-c", _FETCH, str(int(limit))],
        cwd=compose_dir, capture_output=True, text=True, check=True,
    )
    if out.stderr.strip():
        print(out.stderr.strip(), file=sys.stderr)
    rows = json.loads(out.stdout.strip() or "[]")
    # Two documents can share a file name; the id keeps their output dirs apart.
    return [(f"{r['name']}-{r['id'][:8]}", r["text"]) for r in rows]


def entity_counts(extraction: dict) -> dict:
    entities = extraction.get("entities") or extraction
    return {k: len(v) for k, v in entities.items() if isinstance(v, list)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--url", default="http://localhost:8000", help="aiservice base URL")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--language", default="de")
    ap.add_argument("--out", type=Path, default=Path("ab-results"))
    ap.add_argument("--from-db", action="store_true",
                    help="take documents from this deployment's DB instead of files (read-only)")
    ap.add_argument("--compose-dir", type=Path, default=Path("."),
                    help="deployment directory holding compose.yml (--from-db)")
    ap.add_argument("--limit", type=int, default=12, help="how many documents (--from-db)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="leave documents that already have a usable result for this model. "
                         "Resumes a run that hit rate limits without re-sending what worked")
    args = ap.parse_args()

    if args.from_db == bool(args.files):
        ap.error("give either files or --from-db, not both and not neither")

    if args.from_db:
        docs = [(name, text, None) for name, text in
                docs_from_db(args.compose_dir, args.limit)]
        print(f"{len(docs)} document(s) from the database")
    else:
        docs = [(f.stem, None, f) for f in args.files]

    for name, text, path in docs:
        print(f"\n=== {name} ===")
        if text is None and path.suffix in (".md", ".txt"):
            # /ocr takes PDFs and images only, and a probe document is already text.
            text = path.read_text()
            print(f"text file: {len(text)} chars")
        elif text is None:
            ocr = post_file(f"{args.url}/ocr", path)
            text = ocr.get("text", "")
            print(f"OCR: {len(text)} chars, confidence {ocr.get('confidence')}")
        else:
            print(f"stored text: {len(text)} chars")
        if not text.strip():
            print("  no text — skipping")
            continue

        outdir = args.out / name.replace("/", "_")
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "_ocr.txt").write_text(text)

        for model in args.models:
            out_file = outdir / f"{model.replace(':', '_').replace('/', '_')}.json"
            if args.skip_existing and out_file.exists():
                try:
                    if (json.loads(out_file.read_text()).get("entities") or {}):
                        print(f"  {model} … vorhanden, übersprungen")
                        continue
                except json.JSONDecodeError:
                    pass  # unreadable result is no result
            print(f"  {model} …", end="", flush=True)
            result = post_json(
                f"{args.url}/extract-entities",
                {"text": text, "model": model, "language": args.language},
            )
            out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(" ", entity_counts(result))

    print(f"\nJSONs in {args.out}/ — diff them per file to judge quality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
