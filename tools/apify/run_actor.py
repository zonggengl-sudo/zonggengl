#!/usr/bin/env python3
"""Generic Apify Actor runner for the kyniqo nightly batch.

Reads tools/apify/config/actors.json, runs a named target via the Apify
HTTP API (sync run, 300s timeout), and stores the dataset items as JSON.

Usage:
    APIFY_API_TOKEN=apify_api_xxx python3 run_actor.py nex_meta_ads
    python3 run_actor.py --list          # show available targets
    python3 run_actor.py --check         # verify token + list configured actors

Exit codes: 0 ok | 2 no token | 3 bad target | 4 run failed
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
CFG = BASE / "tools" / "apify" / "config" / "actors.json"
API = "https://api.apify.com/v2"


def token() -> str | None:
    return os.environ.get("APIFY_API_TOKEN") or os.environ.get("APIFY_TOKEN")


def load_cfg():
    return json.loads(CFG.read_text(encoding="utf-8"))


def http(method, url, body=None, tok=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    heads = {"Content-Type": "application/json"}
    if tok:
        heads["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, headers=heads, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:500]}
    except Exception as e:
        return 0, {"error": str(e)}


def run_target(name, override_input=None):
    cfg = load_cfg()["targets"]
    if name not in cfg:
        print(f"[x] unknown target '{name}'. available: {', '.join(cfg)}", file=sys.stderr)
        return 3
    t = cfg[name]
    actor = t.get("actor_id")
    if not actor:
        print(f"[!] target '{name}' has no actor_id — {t.get('note','')}", file=sys.stderr)
        return 3

    tok = token()
    if not tok:
        print("[x] APIFY_API_TOKEN not set — skipping", file=sys.stderr)
        return 2

    actor_path = actor.replace("/", "~")
    inp = dict(t.get("default_input", {}))
    if override_input:
        inp.update(override_input)

    print(f"[>] running {actor} for '{name}' ...", file=sys.stderr)
    status, res = http("POST", f"{API}/acts/{actor_path}/run-sync-get-dataset-items"
                       f"?token={tok}&timeout=300&memory=1024",
                       body=inp, timeout=330)
    if status != 200:
        print(f"[x] run failed ({status}): {res.get('error','')[:300]}", file=sys.stderr)
        return 4

    out = BASE / t["output_file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[v] {len(res) if isinstance(res, list) else '?'} items -> {out}", file=sys.stderr)
    return 0


def check(tok):
    status, res = http("GET", f"{API}/actor-tasks?token={tok}&limit=50")
    print(f"token check: HTTP {status}")
    if status == 200 and isinstance(res, dict):
        items = res.get("data", {}).get("items", [])
        print(f"actor tasks visible: {len(items)}")
        for i in items:
            print("  -", i.get("name"), "->", (i.get("act") or {}).get("name", "?"))
    else:
        print("detail:", str(res)[:300])
    return 0 if status == 200 else 4


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "--list":
        for k, v in load_cfg()["targets"].items():
            print(f"{k:28} {v['description']}")
        return 0
    if args[0] == "--check":
        tok = token()
        if not tok:
            print("[x] APIFY_API_TOKEN not set", file=sys.stderr)
            return 2
        return check(tok)
    name = args[0]
    extra = json.loads(args[1]) if len(args) > 1 else None
    return run_target(name, extra)


if __name__ == "__main__":
    sys.exit(main())
