"""Emergency-question detection: regex vs Kev-4B vs one-token logprob.

usage: python scripts/bench-emergency.py SET.json regex
       python scripts/bench-emergency.py SET.json kev URL
       python scripts/bench-emergency.py SET.json logprob URL MODEL [KEY_ENV]
"""
import json, math, os, re, sys, time, urllib.request

KEV_Q = ("Is the person asking what to do right now in an acute medical emergency, "
         "or asking for the emergency plan or the rescue medication dose?")
LP_SYS = (__import__("pathlib").Path(__file__).resolve().parents[1] / "aiservice/prompts/emergency.md").read_text().strip()


def post(url, body, key=None):
    h = {"content-type": "application/json"}
    if key:
        h["authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, json.dumps(body).encode(), h)
    return json.load(urllib.request.urlopen(req, timeout=120))


def regex():
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "backend"))
    from app.routers.chat import _is_emergency
    return lambda q: float(_is_emergency(q, ("Buccolam",)))


def kev(url):
    def f(q):
        r = post(url.rstrip("/") + "/v1/systemone", {"state": q, "model": "kev-latest",
                 "questions": {"e": {"type": "noul", "instructions": KEV_Q}}})
        return r["answers"]["e"]["noul"]
    return f


def logprob(url, model, key_env=None):
    key = os.environ.get(key_env) if key_env else None
    def f(q):
        r = post(url.rstrip("/") + "/chat/completions", {
            "model": model, "max_tokens": 1, "temperature": 0, "logprobs": True, "top_logprobs": 10,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": LP_SYS}, {"role": "user", "content": q}]}, key)
        top = r["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
        p = {"ja": 0.0, "nein": 0.0}
        for t in top:
            w = t["token"].strip().lower()
            k = "ja" if w in ("ja", "j") else "nein" if w and "nein".startswith(w) else None
            if k:  # "nein" arrives as "ne" + "in"
                p[k] += math.exp(t["logprob"])
        s = p["ja"] + p["nein"]
        return p["ja"] / s if s else float("nan")
    return f


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    kind = sys.argv[2]
    score = {"regex": regex, "kev": kev, "logprob": logprob}[kind](*sys.argv[3:])
    rows, t0 = [], time.time()
    for d in data:
        rows.append((score(d["q"]), d["y"], d["q"]))
    ms = (time.time() - t0) / len(data) * 1000
    for th in (0.2, 0.3, 0.5):
        fn = [q for p, y, q in rows if y and not p >= th]
        fp = [q for p, y, q in rows if not y and p >= th]
        print(f"threshold {th}: missed {len(fn)}/{sum(y for _, y, _ in rows)}, false alarms {len(fp)}/{sum(not y for _, y, _ in rows)}")
    print(f"{ms:.0f} ms per question")
    print("\nper question (p, label, q):")
    for p, y, q in rows:
        flag = "MISS" if y and p < 0.2 else "FA" if not y and p >= 0.2 else ""
        print(f"{p:5.2f} {'E' if y else '-'} {flag:4} {q}")
