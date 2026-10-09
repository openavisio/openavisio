#!/usr/bin/env python3
"""Measure how often the right chunk comes back, for whatever embedding model an
aiservice is configured with.

Cosine similarity between a few sentences you made up says nothing. This asks the
only question that matters for RAG: **given a real question, does the chunk that
answers it come back?** The ground truth comes from the corpus rather than from
anyone's judgement — each question is written from one drawn chunk, and that chunk
is the correct answer.

`/embed` uses the model its aiservice is configured with, so comparing two models
means running this twice against two aiservices, with the **same** corpus and the
same questions:

    # once, against the deployment's own documents (read-only, nothing is written back)
    python3 scripts/bench-retrieval.py --from-db --limit 200 \
        --url http://localhost:8001 --gen-url http://<ollama-host>:11434 \
        --questions bench-questions.json --corpus bench-corpus.json

    # again, against an aiservice pointed at the candidate model
    python3 scripts/bench-retrieval.py --url http://other:8000 \
        --questions bench-questions.json --corpus bench-corpus.json

Both files are reused when they exist, which is what makes the second run comparable.
They contain patient text: keep them where the documents already live and delete them
afterwards.

Measured this way on 2026-07-28, 60 questions over 731 chunks from 176 documents:
qwen3-embedding:4b recall@10 0.767, Qwen3-VL-Embedding-8B (truncated to 768d) 0.783,
bge-m3 0.733, paraphrase-multilingual-mpnet-base-v2 0.217.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import urllib.request
from pathlib import Path

# ponytail: characters, not tokens, so this script needs no tokenizer. 2000 chars
# is roughly the 500-token production chunk for German text (aiservice/chunking.py).
# Only consistency across the models being compared matters here; if a benchmark
# ever has to mirror production chunking exactly, import chunk_text instead.
CHUNK_CHARS, OVERLAP_CHARS = 2000, 200

GEN_PROMPT = (
    "Hier ist ein Auszug aus einem medizinischen oder behördlichen Dokument.\n\n"
    "Formuliere GENAU EINE deutsche Frage, die eine Angehörige stellen würde und die "
    "sich nur aus diesem Auszug beantworten lässt. Nenne keine Namen. Verwende nicht "
    "wörtlich denselben Satzbau wie der Auszug. Antworte ausschließlich mit der Frage.\n\n"
    "AUSZUG:\n{chunk}"
)

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
            select(DocumentReference).where(
                DocumentReference.extracted_text.is_not(None),
                DocumentReference.is_deleted == False)  # noqa: E712
        )).scalars().all()
        keks = {}
        for d in rows[:limit]:
            if d.patient_id not in keks:
                keks[d.patient_id] = await get_patient_kek(db, d.patient_id)
            try:
                out.append(decrypt_str(d.extracted_text, keks[d.patient_id]))
            except Exception as exc:
                print(f"skip {d.id}: {exc}", file=sys.stderr)
    print(json.dumps(out))

asyncio.run(main(int(sys.argv[1])))
"""


def post(url: str, payload: dict, timeout: int = 600) -> dict:
    token = os.environ.get("AISERVICE_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-AI-Service-Token"] = token
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def chunk(text: str) -> list[str]:
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + CHUNK_CHARS])
        start += CHUNK_CHARS - OVERLAP_CHARS
    return [c for c in out if len(c.strip()) > 200]


def build_corpus(args) -> list[str]:
    if args.from_db:
        proc = subprocess.run(
            ["docker", "compose", "exec", "-T", "backend",
             "/app/.venv/bin/python", "-c", _FETCH, str(args.limit)],
            cwd=args.compose_dir, capture_output=True, text=True, check=True)
        texts = json.loads(proc.stdout.strip() or "[]")
    else:
        texts = [p.read_text(errors="replace") for p in sorted(Path(args.texts).glob("*.txt"))]
    return [c for t in texts for c in chunk(t)]


def build_questions(corpus: list[str], args) -> list[dict]:
    """One question per drawn chunk, written by a local model over Ollama's HTTP API."""
    random.seed(args.seed)
    out = []
    for n, i in enumerate(random.sample(range(len(corpus)), min(args.questions_n, len(corpus))), 1):
        body = {"model": args.gen_model, "think": False, "stream": False,
                "options": {"temperature": 0, "num_ctx": 8192},
                "messages": [{"role": "user", "content": GEN_PROMPT.format(chunk=corpus[i][:3000])}]}
        req = urllib.request.Request(f"{args.gen_url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            q = json.load(resp)["message"]["content"].strip().split("\n")[-1].strip()
        if len(q) > 15 and "?" in q:
            out.append({"q": q, "gold": i})
        print(f"\r  {n} generiert, {len(out)} brauchbar", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return out


def embed(url: str, texts: list[str], is_query: bool, language: str) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 32):
        out.extend(post(f"{url}/embed", {"texts": texts[i:i + 32],
                                         "is_query": is_query, "language": language})["embeddings"])
        print(f"\r  {min(i + 32, len(texts))}/{len(texts)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return [normalise(v) for v in out]


def normalise(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000", help="aiservice whose embed model is measured")
    ap.add_argument("--from-db", action="store_true", help="corpus from this deployment's documents (read-only)")
    ap.add_argument("--texts", type=Path, help="directory of .txt files instead of --from-db")
    ap.add_argument("--compose-dir", type=Path, default=Path("."))
    ap.add_argument("--limit", type=int, default=200, help="documents to read (--from-db)")
    ap.add_argument("--corpus", type=Path, default=Path("bench-corpus.json"))
    ap.add_argument("--questions", type=Path, default=Path("bench-questions.json"))
    ap.add_argument("--questions-n", type=int, default=60)
    ap.add_argument("--gen-url", default="http://localhost:11434", help="Ollama that writes the questions")
    ap.add_argument("--gen-model", default="qwen3.6:27b-mtp-q4_K_M")
    ap.add_argument("--language", default="de")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.corpus.exists():
        corpus = json.loads(args.corpus.read_text())
        print(f"{len(corpus)} Chunks aus {args.corpus}")
    else:
        if not (args.from_db or args.texts):
            ap.error("give --from-db or --texts to build a corpus")
        corpus = build_corpus(args)
        args.corpus.write_text(json.dumps(corpus, ensure_ascii=False))
        print(f"{len(corpus)} Chunks -> {args.corpus}")

    if args.questions.exists():
        questions = json.loads(args.questions.read_text())
        print(f"{len(questions)} Fragen aus {args.questions}")
    else:
        questions = build_questions(corpus, args)
        args.questions.write_text(json.dumps(questions, ensure_ascii=False))
        print(f"{len(questions)} Fragen -> {args.questions}")

    print("Chunks einbetten …", file=sys.stderr)
    C = embed(args.url, corpus, False, args.language)
    print("Fragen einbetten …", file=sys.stderr)
    Q = embed(args.url, [q["q"] for q in questions], True, args.language)

    ranks = []
    for qv, q in zip(Q, questions):
        scored = sorted(((sum(a * b for a, b in zip(qv, cv)), i) for i, cv in enumerate(C)), reverse=True)
        ranks.append([i for _, i in scored].index(q["gold"]) + 1)
    n = len(ranks)
    ranks_sorted = sorted(ranks)
    print(json.dumps({
        "url": args.url, "chunks": len(corpus), "questions": n,
        "recall@1": round(sum(r == 1 for r in ranks) / n, 3),
        "recall@5": round(sum(r <= 5 for r in ranks) / n, 3),
        "recall@10": round(sum(r <= 10 for r in ranks) / n, 3),
        "median_rank": ranks_sorted[n // 2],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
