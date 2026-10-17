# Releasing

Versions follow [SemVer](https://semver.org): `MAJOR.MINOR.PATCH`.

**Pre-1.0 (`0.x`):** the project is not yet API/schema-stable, so a **minor**
bump may carry breaking changes and a **patch** is reserved for backward-safe
fixes. Once things settle, `1.0.0` starts the normal MAJOR-breaks contract.

The version lives in three places that must stay in lockstep:

- `backend/pyproject.toml` → `version`
- `frontend/package.json` → `version`
- the git tag `vX.Y.Z`

## Cutting a release

```bash
# 1. bump both manifests to the new version (same value), commit via PR, merge
# 2. from an up-to-date master:
git tag -a vX.Y.Z -m "Release vX.Y.Z — <one-line summary>"
git push origin vX.Y.Z
```

Every tag is a plain `vX.Y.Z`, never a pre-release suffix like `-beta3`: the tag is also the
image tag a customer's Deployment runs. Pre-1.0 already says "not yet stable". The
`v0.1.0-beta*` tags up to `v0.1.0-beta17` (17 Oct 2026) stay as history; `v0.2.0` follows them.

The tag is annotated (not lightweight) so it carries a message and a date. Then
publish it to the public repository (ADR 032):

```bash
scripts/make-public-snapshot.sh vX.Y.Z        # refuses if anything internal survives
git -C /tmp/openavisio-public-vX.Y.Z push origin main vX.Y.Z
```

`v0.1.0` (18 Jul 2026) was the first tagged release — the point where the
Go-Live blockers were cleared.

<!-- Deliberately no CI release automation, changelog generator, or GitHub-style
     release pages yet: one solo maintainer, tags are enough. Add them when a
     second person needs to cut a release. (ADR 024, ADR 032) -->
