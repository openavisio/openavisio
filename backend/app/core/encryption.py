"""Document envelope encryption and key wrapping.

Key hierarchy (ADR-031):
    blob + extracted_text + extraction_json + chunk content   (ciphertext)
        ▲ AES-GCM, per-document DEK
    document DEK                                               (encrypted_dek)
        ▲ AES-GCM, per-patient KEK  (see app.core.patient_keys)
    patient KEK                                                (patient_keys row)
        ▲ AES-GCM, master KEK
    master KEK                                                 (DOCUMENT_ENCRYPTION_KEY env)

The wrap/encrypt helpers take the wrapping key explicitly so the same code
serves both the master KEK (settings) and per-patient KEKs (documents).
Storage files contain only ciphertext: [12-byte nonce][AES-GCM ciphertext+tag].
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_kek() -> bytes:
    """The master KEK — root of the hierarchy. Held out-of-band in the env.

    This is the only seam a future KMS/HSM has to replace (ADR-031)."""
    from app.core.config import settings
    key_b64 = settings.document_encryption_key
    if not key_b64:
        raise RuntimeError(
            "DOCUMENT_ENCRYPTION_KEY is not set. "
            'Generate one with: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"'
        )
    return base64.b64decode(key_b64)


def wrap_dek(dek: bytes, kek: bytes) -> bytes:
    """Encrypt a 32-byte DEK under a KEK. Returns [nonce(12)][ct+tag(48)] = 60 bytes."""
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, None)


def unwrap_dek(wrapped: bytes, kek: bytes) -> bytes:
    nonce, ct = wrapped[:12], wrapped[12:]
    return AESGCM(kek).decrypt(nonce, ct, None)


_STR_PREFIX = "enc:v1:"


def encrypt_str(plaintext: str, key: bytes) -> str:
    """Encrypt a string under `key`. Returns 'enc:v1:<base64(nonce+ct+tag)>'.

    The prefix lets decrypt_str pass through legacy plaintext during migration."""
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return _STR_PREFIX + base64.b64encode(nonce + ct).decode()


def decrypt_str(value: str | None, key: bytes) -> str | None:
    """Inverse of encrypt_str. Values without the enc: prefix are returned
    unchanged (legacy plaintext), so reads keep working before migration."""
    if not value or not value.startswith(_STR_PREFIX):
        return value
    raw = base64.b64decode(value[len(_STR_PREFIX):])
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()


def encrypt_setting(plaintext: str) -> str:
    """Encrypt a secret setting value under the master KEK (#50)."""
    return encrypt_str(plaintext, _get_kek())


def decrypt_setting(value: str) -> str:
    return decrypt_str(value, _get_kek())


def encrypt_document(data: bytes, kek: bytes) -> tuple[bytes, bytes]:
    """Encrypt document bytes under a fresh DEK wrapped by `kek` (the patient KEK).
    Returns (ciphertext_blob, wrapped_dek)."""
    dek = os.urandom(32)
    nonce = os.urandom(12)
    ct = AESGCM(dek).encrypt(nonce, data, None)
    return nonce + ct, wrap_dek(dek, kek)


def decrypt_document(ciphertext_blob: bytes, wrapped_dek: bytes, kek: bytes) -> bytes:
    dek = unwrap_dek(wrapped_dek, kek)
    nonce, ct = ciphertext_blob[:12], ciphertext_blob[12:]
    return AESGCM(dek).decrypt(nonce, ct, None)


if __name__ == "__main__":
    # ponytail: one round-trip self-check across the whole hierarchy
    master = os.urandom(32)
    patient_kek = os.urandom(32)
    wrapped = wrap_dek(patient_kek, master)
    assert unwrap_dek(wrapped, master) == patient_kek
    blob, wdek = encrypt_document(b"lab report bytes", patient_kek)
    assert decrypt_document(blob, wdek, patient_kek) == b"lab report bytes"
    enc = encrypt_str("Kreatinin 1.2 mg/dl", patient_kek)
    assert enc.startswith(_STR_PREFIX)
    assert decrypt_str(enc, patient_kek) == "Kreatinin 1.2 mg/dl"
    assert decrypt_str("legacy plaintext", patient_kek) == "legacy plaintext"  # pass-through
    assert decrypt_str(None, patient_kek) is None
    # wrong key must fail (crypto-shred: destroying the patient KEK makes this unrecoverable)
    try:
        decrypt_document(blob, wdek, os.urandom(32))
        raise SystemExit("FAIL: decrypted with wrong key")
    except Exception:
        pass
    print("encryption self-check OK")
