#!/usr/bin/env python3
"""Compare live Shopify blog publish times with the Feishu table and sync.

Feishu table: KYNIQO wiki > 广告相关 > Shopify文章统计（blog posts） > 文章统计
Fields: 文章标题(text) | 文章链接(text) | 上线时间(datetime)

Usage:
    python3 sync_shopify_to_feishu.py            # dry-run: print diff
    python3 sync_shopify_to_feishu.py --apply    # write updates to Feishu

Matching: by article handle parsed out of 文章链接 (falls back to title slug).
Only updates 上线时间 when the live value differs by more than --tolerance
(default 60 seconds). Non-matching / new articles are reported.
"""
import csv
import difflib
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "shopify"
LARK = "/Users/lizonggeng/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
BASE_TOKEN = "GEkAbl2knauH1ps1uJxcJ8rMnCm"
TABLE_ID = "tblv6a9UodQ0Ca7I"
CST = timezone(timedelta(hours=8))


def lark(*args):
    env = {k: v for k, v in __import__("os").environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
    r = subprocess.run([LARK, *args], capture_output=True, text=True, env=env, timeout=120)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"ok": False, "error": r.stdout[:400] + r.stderr[:400]}


def load_live():
    rows = list(csv.DictReader(open(DATA / "blog_posts_dates_kyniqo.csv", encoding="utf-8")))
    out = {}
    for r in rows:
        if r["status"] != "OK" or not r["published"]:
            continue
        out[r["handle"]] = {
            "title": html.unescape(r["title"]), "url": r["url"],
            "published": datetime.fromisoformat(r["published"]).astimezone(CST),
        }
    return out


def handle_of(url_cell):
    """Feishu stores markdown-ish links; pull out the article handle.

    Two shapes seen in the wild:
      [https://kyniqo.com/blogs/news/<handle>](https://kyniqo.com/blogs/news/<handle>)
      [https://kyniqo.com\u203a blogs \u203a news \u203a <handle>](https://kyniqo.com)
    """
    s = html.unescape(url_cell or "")
    s = s.replace("\u203a", "/").replace(">", "/")
    s = re.sub(r"\s*/\s*", "/", s)
    m = re.search(r"/blogs/[^/]+/([a-z0-9\-]+)", s)
    if m:
        return m.group(1)
    m = re.search(r"([a-z0-9\-]{8,})\]?\s*\(?\s*$", s.strip())
    return m.group(1) if m else ""


def norm_title(t):
    t = html.unescape(t or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_index(live):
    return {norm_title(v["title"]): h for h, v in live.items()}


def load_feishu():
    # 显式放大 limit（默认仅 100，json 格式上限 200），避免去重漏看已有记录
    res = lark("base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", TABLE_ID, "--limit", "200", "--format", "json")
    if not res.get("ok"):
        print("[x] feishu read failed:", res.get("error"), file=sys.stderr)
        sys.exit(1)
    d = res["data"]
    if d.get("has_more"):
        print("[!] 记录数超过 200 且仍有更多，去重可能不完整，请改用 ndjson 分页", file=sys.stderr)
    recs = []
    for rid, row in zip(d["record_id_list"], d["data"]):
        recs.append({"record_id": rid, "title": row[0], "url": row[1], "time": row[2]})
    return recs


def main():
    apply = "--apply" in sys.argv
    tol = 60
    live = load_live()
    fei = load_feishu()
    print(f"[i] live articles: {len(live)} | feishu records: {len(fei)}")

    updates, missing, unmatched = [], [], []
    used = set()
    tidx = title_index(live)
    tkeys = list(tidx)
    for rec in fei:
        h = handle_of(rec["url"])
        if h not in live:
            # fallback: article may have been renamed - match on title
            m = difflib.get_close_matches(norm_title(rec["title"]), tkeys, n=1, cutoff=0.72)
            if m:
                h = tidx[m[0]]
            else:
                unmatched.append(rec)
                continue
        used.add(h)
        lv = live[h]
        if not rec["time"]:
            updates.append((rec["record_id"], h, None, lv["published"]))
            continue
        cur = datetime.fromisoformat(rec["time"].replace(".000", "")).astimezone(CST)
        if abs((lv["published"] - cur).total_seconds()) > tol:
            updates.append((rec["record_id"], h, cur, lv["published"]))
    for h, v in live.items():
        if h not in used:
            missing.append((h, v))

    print(f"\n== DIFF ==  need update: {len(updates)} | not in feishu: {len(missing)} "
          f"| unmatched feishu rows: {len(unmatched)}")
    for rid, h, cur, new in updates:
        c = cur.strftime("%Y-%m-%d %H:%M") if cur else "(empty)"
        print(f"  ~ {h[:52]:52} {c} -> {new.strftime('%Y-%m-%d %H:%M')}")
    for h, v in missing:
        print(f"  + {h[:52]:52} NEW  {v['published'].strftime('%Y-%m-%d %H:%M')}  {v['title'][:40]}")
    for rec in unmatched:
        print(f"  ? unmatched: {(rec['title'] or rec['url'])[:70]}")

    out = {"updates": [{"record_id": r, "handle": h,
                        "old": c.strftime("%Y-%m-%d %H:%M:%S%z") if c else None,
                        "new": n.strftime("%Y-%m-%d %H:%M:%S%z")}
                       for r, h, c, n in updates],
           "missing": [{"handle": h, "title": v["title"], "url": v["url"],
                        "published": v["published"].isoformat()} for h, v in missing],
           "unmatched": [{"record_id": r["record_id"], "title": r["title"], "url": r["url"]}
                         for r in unmatched]}
    (DATA / "feishu_sync_diff.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[v] diff -> {DATA/'feishu_sync_diff.json'}")

    if not apply:
        print("[i] dry-run; pass --apply to write")
        return

    # --- apply time corrections (one batch call) ---
    if updates:
        payload = {"update_records": {rid: {"上线时间": int(new.timestamp() * 1000)}
                                      for rid, h, cur, new in updates}}
        r = lark("base", "+record-batch-update", "--base-token", BASE_TOKEN,
                 "--table-id", TABLE_ID, "--json",
                 json.dumps(payload, ensure_ascii=False), "--format", "json")
        if r.get("ok"):
            print(f"[v] updated {len(updates)} 上线时间 fields")
        else:
            print(f"[x] batch update failed: {str(r.get('error'))[:400]}", file=sys.stderr)
            (DATA / "pending_feishu_updates.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    saved locally -> {DATA/'pending_feishu_updates.json'} (待同步飞书)")

    # --- add articles missing from feishu ---
    if missing:
        recs = [{"fields": {"文章标题": v["title"],
                            "文章链接": v["url"],
                            "上线时间": int(v["published"].timestamp() * 1000)}}
                for _, v in missing]
        r = lark("base", "+record-batch-create", "--base-token", BASE_TOKEN,
                 "--table-id", TABLE_ID, "--json",
                 json.dumps({"create_records": [x["fields"] for x in recs]},
                            ensure_ascii=False), "--format", "json")
        if r.get("ok"):
            print(f"[v] created {len(recs)} new records")
        else:
            print(f"[x] create failed: {str(r.get('error'))[:300]}", file=sys.stderr)
            (DATA / "pending_feishu_records.json").write_text(
                json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    saved locally -> {DATA/'pending_feishu_records.json'} (待同步飞书)")


if __name__ == "__main__":
    main()
