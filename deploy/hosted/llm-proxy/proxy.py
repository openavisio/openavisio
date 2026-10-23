"""The LLM proxy of a hosted box (#375): every Deployment's AI calls pass through here to IONOS.

It holds the one provider token, so a Deployment only has its own key, and it records per
request who called which model with how many tokens. It never stores or logs a prompt or an
answer: those are health data, and the only things read out of a body are the model name and
the `usage` block.

    python proxy.py                 serve on :8080
    python proxy.py report [YYYY-MM] tokens per Deployment and model, this month by default

/data/keys holds one line per Deployment, "<id> <sha256 of its key>" (deploy/hosted/proxy-key.sh).
"""

import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("UPSTREAM", "https://openai.inference.de-txl.ionos.com").rstrip("/")
DATA = os.environ.get("DATA_DIR", "/data")
PASS_BACK = ("Content-Type", "Retry-After", "X-RateLimit-Limit-Requests",
             "X-RateLimit-Remaining-Requests", "X-RateLimit-Reset-Requests")

_keys: dict[str, str] = {}
_keys_mtime = 0.0
_db_lock = threading.Lock()


def _deployment(auth_header: str | None) -> str | None:
    """The Deployment a key belongs to; the file is re-read when it changes."""
    global _keys, _keys_mtime
    path = os.path.join(DATA, "keys")
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0
    if mtime != _keys_mtime:
        lines = open(path).read().split("\n") if mtime else []
        _keys = {h: i for i, h in (ln.split() for ln in lines if ln.strip())}
        _keys_mtime = mtime
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return _keys.get(hashlib.sha256(auth_header[7:].strip().encode()).hexdigest())


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(os.path.join(DATA, "usage.db"))
    db.execute("""CREATE TABLE IF NOT EXISTS usage (
        ts TEXT, deployment TEXT, model TEXT, path TEXT, status INTEGER,
        prompt_tokens INTEGER, completion_tokens INTEGER, ms INTEGER)""")
    return db


def _record(*row) -> None:
    with _db_lock, _db() as db:
        db.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now(timezone.utc).isoformat(timespec="seconds"), *row))


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *_):  # the default line holds the path and nothing else, but stays quiet
        pass

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, b'{"ok":true}', {"Content-Type": "application/json"})
        self._forward(None)

    def do_POST(self):
        self._forward(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

    def _send(self, status: int, body: bytes, headers: dict) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self, body: bytes | None) -> None:
        who = _deployment(self.headers.get("Authorization"))
        if who is None:
            return self._send(401, b'{"error":"unknown key"}', {"Content-Type": "application/json"})
        if not self.path.startswith("/v1/"):
            return self._send(404, b'{"error":"not found"}', {"Content-Type": "application/json"})
        model = ""
        if body:
            try:
                model = str(json.loads(body).get("model") or "")
            except (ValueError, AttributeError):
                pass
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=self.command, headers={
            "Authorization": f"Bearer {os.environ['IONOS_API_KEY']}",
            "Content-Type": self.headers.get("Content-Type", "application/json"),
        })
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                status, data, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, data, headers = e.code, e.read(), e.headers
        except OSError:
            status, data, headers = 502, b'{"error":"upstream unreachable"}', {"Content-Type": "application/json"}
        usage = {}
        if status == 200 and body:
            try:
                usage = json.loads(data).get("usage") or {}
            except (ValueError, AttributeError):
                pass
        if body:  # GET /v1/models is not usage
            _record(who, model, self.path, status, usage.get("prompt_tokens"),
                    usage.get("completion_tokens"), int((time.monotonic() - start) * 1000))
        self._send(status, data, {k: headers[k] for k in PASS_BACK if headers.get(k)})


def report(month: str) -> str:
    rows = _db().execute("""SELECT deployment, model, COUNT(*), SUM(status = 429), SUM(status >= 400),
        COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0)
        FROM usage WHERE ts LIKE ? GROUP BY deployment, model ORDER BY deployment, model""",
                         (month + "%",)).fetchall()
    out = [f"{'DEPLOYMENT':<12} {'MODEL':<32} {'CALLS':>7} {'429':>5} {'ERR':>5} {'IN':>11} {'OUT':>10}"]
    out += [f"{d:<12} {m[:32]:<32} {n:>7} {r:>5} {e:>5} {i:>11} {o:>10}" for d, m, n, r, e, i, o in rows]
    return "\n".join(out)


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"]:
        print(report(sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone.utc).strftime("%Y-%m")))
    else:
        os.environ["IONOS_API_KEY"]  # fail at start, not on the first request
        ThreadingHTTPServer(("", 8080), Proxy).serve_forever()
