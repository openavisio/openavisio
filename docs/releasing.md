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

The tag is annotated (not lightweight) so it carries a message and a date. The
Codeberg mirror picks it up automatically.

`v0.1.0` (18 Jul 2026) was the first tagged release — the point where the
Go-Live blockers were cleared.

<!-- Deliberately no CI release automation, changelog generator, or GitHub-style
     release pages yet: one solo maintainer, tags are enough. Add them when a
     second person needs to cut a release. (ADR 024, ADR 032) -->
