# OpenAvisio License File Format

## Overview

An OpenAvisio license is a JSON file signed with Ed25519. It is issued by the OpenAvisio project
for Commercial tier deployments and uploaded by an admin via the Admin → License page.

## File format

```json
{
  "v": 1,
  "tier": "commercial",
  "issued_to": "Name of the licensed organisation",
  "iat": 1749600000,
  "exp": 1781136000,
  "sig": "<base64-encoded Ed25519 signature>"
}
```

The signature covers the canonical JSON of all fields except `sig`
(`json.dumps` with `sort_keys=True`, no extra whitespace).

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `v` | int | yes | Format version — always `1` |
| `tier` | string | yes | Always `"commercial"` |
| `issued_to` | string | yes | Name of the licensed organisation |
| `iat` | int (Unix ts) | yes | Issue timestamp |
| `exp` | int (Unix ts) | yes | Expiry timestamp |
| `sig` | string | yes | Base64-encoded Ed25519 signature |

## Grace Period

A Commercial license that has passed its `exp` but is within 30 days of expiry still grants
Commercial tier limits. After the grace period the installation reverts to Personal tier defaults
(10 Patients, 3 Users).

## Verification

The backend verifies the Ed25519 signature using a public key. The embedded default is the
**production public key** — only licenses signed by the OpenAvisio project private key (held
offline, see avisiohub) will validate on a standard deployment.

Operators can override via the `LICENSE_PUBLIC_KEY` environment variable (raw 32 bytes, base64).
The only reason to do this is local development and testing (see below).

## Personal Tier Defaults (no license required)

- Maximum 10 Patients
- Maximum 3 Users
- AGPL-3.0 applies

## Generating a Test License (development only)

**Generate your own key pair.** A dev private key used to be committed here — a
`BEGIN PRIVATE KEY` block in a public repository fails any security review on
sight, and it was never needed: the key signs nothing but your own local test
licences.

```bash
# your own throwaway dev key — keep it OUT of the repo
openssl genpkey -algorithm ed25519 -out /tmp/dev-license.pem

# the matching public key, base64, for LICENSE_PUBLIC_KEY
openssl pkey -in /tmp/dev-license.pem -pubout -outform DER | tail -c 32 | base64
```

Then generate a test license token:

```python
# Requires: pip install cryptography
import base64, json, time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

private_key = Ed25519PrivateKey.from_private_bytes(
    # extract raw 32-byte private key scalar from PEM:
    __import__('cryptography').hazmat.primitives.serialization.load_pem_private_key(
        open("/tmp/dev-license.pem", "rb").read(), password=None
    ).private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
)

payload = {
    "v": 1,
    "tier": "commercial",
    "issued_to": "My Test Org",
    "iat": int(time.time()),
    "exp": int(time.time()) + 365 * 86400,
}
message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
sig = base64.b64encode(private_key.sign(message)).decode()
license_json = json.dumps({**payload, "sig": sig}, indent=2)
print(license_json)
```

Set `LICENSE_PUBLIC_KEY=56E6x74g4kfNQOdok6JxmhHbmnaX9BMJD/syth+1mDA=` in `.env` to validate
dev licenses. This key does not validate against the embedded production key.

## Issuing a Production License

Use the production private key (kept offline in avisiohub) with the same script above,
without overriding `LICENSE_PUBLIC_KEY` on the deployment.
