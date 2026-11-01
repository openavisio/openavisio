"""Print the backend's OpenAPI for `pnpm api-types` (frontend/src/lib/api-schema.ts).

A field with a default is optional in a request, but a response always carries every
field, so in schemas no request reaches all fields are marked required.

    cd backend && uv run python ../scripts/openapi.py > /tmp/openapi.json
"""

import json
import sys

sys.path.insert(0, ".")
from app.main import app  # noqa: E402

spec = app.openapi()
schemas = spec["components"]["schemas"]


def refs(node):
    if isinstance(node, dict):
        if "$ref" in node:
            yield node["$ref"].rsplit("/", 1)[-1]
        for v in node.values():
            yield from refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from refs(v)


inputs: set[str] = set()
todo = [
    r
    for path in spec["paths"].values()
    for op in path.values()
    for part in (op.get("requestBody", {}), op.get("parameters", []))
    for r in refs(part)
]
while todo:
    name = todo.pop()
    if name not in inputs:
        inputs.add(name)
        todo.extend(refs(schemas[name]))

for name, schema in schemas.items():
    if name in inputs:
        continue
    if "properties" in schema:
        schema["required"] = sorted(schema["properties"])

json.dump(spec, sys.stdout)


def _check():
    assert "expenses" not in schemas["VerifyDocumentRequest"].get("required", [])
    assert {"is_favorite", "correspondent"} <= set(schemas["DocumentDto"]["required"])


_check()
