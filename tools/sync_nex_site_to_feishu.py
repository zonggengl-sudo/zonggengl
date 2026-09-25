#!/usr/bin/env python3
"""Sync crawled Nex Playground site pages into Feishu table 独立站内容.

Feishu: KYNIQO wiki > 广告相关 >
        Nex Playground Meta广告分析、独立站内容、Facebook主页内容汇总
        > table 独立站内容 (tblIXNJ1BvTYEe4y)

Fields: 页面链接(text) | 标题(text) | 页面(text) |
        内容类型(select) | 文案内容(text)

Existing rows are matched on URL; only genuinely new pages are created.
Content type is mapped from the URL path onto the table's existing options.

Usage:
    python3 sync_nex_site_to_feishu.py           # dry-run
    python3 sync_nex_site_to_feishu.py --apply   # create missing records
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "nex_playground"
LARK = "/Users/lizonggeng/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"
BASE_TOKEN = "X6HgblAEIaabebsr3GQcp8qRnQg"
TABLE_ID = "tblIXNJ1BvTYEe4y"
ORIGIN = "https://www.nexplayground.com"
MAX_COPY = 8000  # feishu text cell is generous; keep payload sane

OPTIONS = ["首页文案", "游戏目录", "产品介绍", "订阅服务", "购买页面", "用户故事", "游戏详情",
           "品牌", "法务/合规"]  # 后两项于 2026-09-25 追加，用于收纳 about/privacy 等品牌与法务页面


def lark(*args):
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
    r = subprocess.run([LARK, *args], capture_output=True, text=True, env=env, timeout=180)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"ok": False, "error": (r.stdout + r.stderr)[:400]}


def classify(path):
    if path in ("/", ""):
        return "首页文案", "首页"
    seg = path.strip("/").split("/")
    head, n = seg[0], len(seg)
    if head == "games":
        return ("游戏目录", "游戏目录") if n == 1 else ("游戏详情", "游戏详情")
    if head == "shop":
        return "购买页面", "购买"
    if head in ("play-pass",):
        return "订阅服务", "Play Pass订阅"
    if head in ("playground", "why-playground"):
        return "产品介绍", "产品介绍"
    if head in ("community",):
        return "用户故事", "用户故事"
    # 法务/合规类（2026-09-25 新增）
    if head in ("privacy", "refund", "trust", "safety-and-privacy") or \
            path.startswith("/learn/compliance-regulatory"):
        return "法务/合规", "法务合规"
    # 品牌类（2026-09-25 新增）
    if head in ("about", "careers", "contact", "mission", "playground-for-good", "japan-2026"):
        return "品牌", "品牌"
    # 门店查询归入购买相关
    if head == "find-in-stores":
        return "购买页面", "门店查询"
    return None, head


def main():
    apply = "--apply" in sys.argv
    pages = json.loads((DATA / "site_pages.json").read_text(encoding="utf-8"))
    pages = [p for p in pages if p.get("status") == "OK" and p.get("文案内容")]

    # existing rows -> set of URLs
    # 显式放大 limit（默认仅 100，json 格式上限 200）；读取失败或为空必须中止，
    # 否则 existing 为空会把全部页面当成新增重复插入
    res = lark("base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", TABLE_ID, "--limit", "200", "--format", "json")
    if not res.get("ok"):
        print("[x] feishu read failed, abort to avoid duplicate insert:",
              res.get("error"), file=sys.stderr)
        sys.exit(1)
    d = res["data"]
    if d.get("has_more"):
        print("[!] 记录数超过 200 且仍有更多，去重可能不完整，请改用 ndjson 分页", file=sys.stderr)
    existing = set()
    names = d.get("fields", [])
    idx = names.index("页面链接") if "页面链接" in names else 0
    for row in d.get("data", []):
        m = re.search(r"https?://[^\s\)\]›]+", (row[idx] or "").replace("\u203a", "/"))
        if m:
            existing.add(m.group(0).rstrip("/"))
    if not existing:
        print("[x] 未读到任何已有记录，中止以避免重复写入", file=sys.stderr)
        sys.exit(1)
    print(f"[i] crawled pages: {len(pages)} | feishu existing urls: {len(existing)}")

    new, skipped = [], []
    for p in pages:
        url = p["页面链接"].rstrip("/")
        if url in existing:
            continue
        path = url.replace(ORIGIN, "") or "/"
        ctype, page = classify(path)
        if not ctype:
            skipped.append(path)
            continue
        new.append({"页面链接": p["页面链接"], "标题": p["标题"][:400], "页面": page,
                    "内容类型": ctype, "文案内容": p["文案内容"][:MAX_COPY]})

    print(f"\n== SYNC ==  new: {len(new)} | skipped(no category): {len(skipped)}")
    from collections import Counter
    print("  by type:", dict(Counter(x["内容类型"] for x in new)))
    for x in new[:12]:
        print(f"  + [{x['内容类型']}] {x['页面链接'].replace(ORIGIN,'') or '/'}")
    if skipped:
        print(f"  skipped paths: {', '.join(skipped[:12])}")

    (DATA / "feishu_site_pending.json").write_text(
        json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[v] payload -> {DATA/'feishu_site_pending.json'}")

    if not apply:
        print("[i] dry-run; pass --apply to write")
        return

    created = 0
    for i in range(0, len(new), 20):  # feishu batch-create caps around 500; 20 keeps it safe
        chunk = new[i:i + 20]
        r = lark("base", "+record-batch-create", "--base-token", BASE_TOKEN,
                 "--table-id", TABLE_ID, "--json",
                 json.dumps({"create_records": chunk}, ensure_ascii=False),
                 "--format", "json")
        if r.get("ok"):
            created += len(chunk)
        else:
            print(f"  [x] batch {i//20} failed: {str(r.get('error'))[:300]}", file=sys.stderr)
    print(f"[v] created {created}/{len(new)} records in 独立站内容")


if __name__ == "__main__":
    main()
