"""Key rotation script for document envelope encryption.

Re-wraps all per-document DEKs under a new KEK without touching storage files.

OFFLINE rotation (ADR-022). Order matters: a running backend still holds the
OLD KEK in memory and cannot unwrap DEKs re-wrapped under the new KEK, so every
document read fails until it is restarted. Required order:

    1. Stop backend + celery workers.
    2. python -m app.scripts.rotate_deks --new-key <base64-32B> --confirm-services-stopped
    3. Set DOCUMENT_ENCRYPTION_KEY in .env to the new key.
    4. Start backend + celery workers.

The script refuses to run without --confirm-services-stopped.

Generate a new key:
    python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
"""

import argparse
import asyncio
import base64
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.document import DocumentReference


def _unwrap(wrapped: bytes, kek: bytes) -> bytes:
    nonce, ct = wrapped[:12], wrapped[12:]
    return AESGCM(kek).decrypt(nonce, ct, None)


def _wrap(dek: bytes, kek: bytes) -> bytes:
    import os
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, None)


async def rotate(new_key_b64: str) -> None:
    if not settings.document_encryption_key:
        print("ERROR: DOCUMENT_ENCRYPTION_KEY is not set in .env (current key).", file=sys.stderr)
        sys.exit(1)

    old_kek = base64.b64decode(settings.document_encryption_key)
    new_kek = base64.b64decode(new_key_b64)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentReference).where(DocumentReference.encrypted_dek.is_not(None))
        )
        docs = result.scalars().all()

        rotated = 0
        failed = 0
        for doc in docs:
            try:
                dek = _unwrap(doc.encrypted_dek, old_kek)
                doc.encrypted_dek = _wrap(dek, new_kek)
                doc.kek_version = (doc.kek_version or 1) + 1
                rotated += 1
            except Exception as exc:
                print(f"WARNING: could not rotate DEK for document {doc.id}: {exc}", file=sys.stderr)
                failed += 1

        if failed:
            print(f"ERROR: {failed} DEK(s) could not be rotated. Aborting without commit.", file=sys.stderr)
            sys.exit(1)

        await db.commit()
        print(f"Rotated {rotated} DEK(s) successfully.")
        print(f"\nNext steps (services should already be stopped):")
        print(f"  1. Set DOCUMENT_ENCRYPTION_KEY in .env to: {new_key_b64}")
        print(f"  2. Start backend and celery workers.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-wrap document DEKs under a new KEK.")
    parser.add_argument("--new-key", required=True, help="Base64-encoded 32-byte new KEK")
    parser.add_argument(
        "--confirm-services-stopped",
        action="store_true",
        help="Assert backend + celery are stopped. Rotation refuses to run without it.",
    )
    args = parser.parse_args()

    if not args.confirm_services_stopped:
        print(
            "ERROR: refusing to rotate while services may be running.\n"
            "Stop backend + celery first, then re-run with --confirm-services-stopped.\n"
            "(A running backend holds the old KEK and would fail every document read "
            "after rotation until restarted.)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        raw = base64.b64decode(args.new_key)
    except Exception:
        print("ERROR: --new-key is not valid base64.", file=sys.stderr)
        sys.exit(1)
    if len(raw) != 32:
        print(f"ERROR: --new-key must decode to exactly 32 bytes (got {len(raw)}).", file=sys.stderr)
        sys.exit(1)

    asyncio.run(rotate(args.new_key))


if __name__ == "__main__":
    main()
