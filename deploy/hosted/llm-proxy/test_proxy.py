"""The proxy against a fake upstream: keys, pass-through, usage rows, no content stored (#375)."""

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET_PROMPT = "Epilepsie seit 2019, Valproat 300 mg"


class _Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers["Authorization"] != "Bearer ionos-token":
            out, status, extra = b'{"error":"bad token"}', 401, {}
        elif body["model"] == "busy":
            out, status, extra = b'{"error":"rate"}', 429, {"Retry-After": "2"}
        else:
            out = json.dumps({"choices": [{"message": {"content": "Antwort"}}],
                              "usage": {"prompt_tokens": 120, "completion_tokens": 7}}).encode()
            status, extra = 200, {}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in extra.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _post(port, key, model):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", method="POST",
                                 data=json.dumps({"model": model, "messages": [{"role": "user", "content": SECRET_PROMPT}]}).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_proxy():
    data = tempfile.mkdtemp()
    with open(os.path.join(data, "keys"), "w") as f:
        f.write(f"k7f3x9q2 {hashlib.sha256(b'deployment-key').hexdigest()}\n")
    upstream = _serve(_Upstream)
    os.environ.update(DATA_DIR=data, IONOS_API_KEY="ionos-token",
                      UPSTREAM=f"http://127.0.0.1:{upstream.server_port}")
    import proxy  # reads the environment at import
    port = _serve(proxy.Proxy).server_port

    status, _, body = _post(port, "deployment-key", "Qwen/Qwen3.8-27B")
    assert status == 200 and json.loads(body)["choices"][0]["message"]["content"] == "Antwort"

    status, headers, _ = _post(port, "deployment-key", "busy")
    assert status == 429 and headers["Retry-After"] == "2"  # #374 needs it

    status, _, _ = _post(port, "someone-else", "Qwen/Qwen3.8-27B")
    assert status == 401

    rows = sqlite3.connect(os.path.join(data, "usage.db")).execute(
        "SELECT deployment, model, status, prompt_tokens, completion_tokens FROM usage ORDER BY rowid").fetchall()
    assert rows == [("k7f3x9q2", "Qwen/Qwen3.8-27B", 200, 120, 7), ("k7f3x9q2", "busy", 429, None, None)]
    stored = open(os.path.join(data, "usage.db"), "rb").read()
    assert SECRET_PROMPT.encode() not in stored and b"Antwort" not in stored
    assert "k7f3x9q2" in proxy.report(datetime.now(timezone.utc).strftime("%Y-%m"))


if __name__ == "__main__":
    test_proxy()
    print("ok")
