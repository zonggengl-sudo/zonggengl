#!/usr/bin/env python3
"""Crawl Nex Playground marketing-site pages and extract structured copy.

Produces rows shaped like the Feishu table
「Nex Playground Meta广告分析、独立站内容、Facebook主页内容汇总 / Nex独立站内容」:
    页面链接 | 标题 | 页面 | 内容类型 | 文案内容

Only English (default-locale) marketing pages are crawled; /blog/* and the
/en-ca /en-gb /en-ie /fr-ca locale trees are skipped.

Usage: python3 crawl_nex_site.py [--limit N]
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "nex_playground"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
ORIGIN = "https://www.nexplayground.com"
SKIP_PREFIX = ("/en-ca", "/en-gb", "/en-ie", "/fr-ca", "/blog", "/api", "/preview")

# nav/footer boilerplate paragraphs seen on every page
BOILER = re.compile(r"^(Shop|Learn|Support|About|Legal|Cart|Menu|Close|Search)\b", re.I)


def fetch(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return url, r.geturl(), r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == 2:
                return url, url, f"__ERR__{e}"
            time.sleep(1.5 * (attempt + 1))
    return url, url, "__ERR__"


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def extract(url, final_url, doc):
    """Return (title, copy) where copy is '[H2] heading\\nparagraph ...'."""
    if doc.startswith("__ERR__"):
        return None, None, doc
    m = re.search(r"<title>(.*?)</title>", doc, re.S)
    title = clean(m.group(1)) if m else ""
    h1s = [clean(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", doc, re.S)]
    h1s = [h for h in h1s if h]

    # walk headings + paragraphs in document order
    parts, seen = [], set()
    for m in re.finditer(r"<(h[1-3])[^>]*>(.*?)</\1>|<p[^>]*>(.*?)</p>", doc, re.S):
        if m.group(2) is not None:
            t = clean(m.group(2))
            if not t or BOILER.match(t) or len(t) > 220:
                continue
            if t in seen:
                continue
            seen.add(t)
            parts.append(f"[{m.group(1).upper()}] {t}")
        else:
            t = clean(m.group(3))
            if not t or BOILER.match(t) or len(t) < 15:
                continue
            if t in seen:
                continue
            seen.add(t)
            parts.append(t)
    return title, (h1s[0] if h1s else title), "\n".join(parts)


def page_name(path):
    if path in ("/", ""):
        return "首页"
    seg = path.strip("/").split("/")[0]
    return {"games": "游戏", "shop": "商店", "play-pass": "Play Pass订阅",
            "playground": "产品介绍", "learn": "学习中心"}.get(seg, seg)


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    locs = [l for l in re.findall(r"<loc>(.*?)</loc>", (OUT / "sitemap.xml").read_text())]
    urls = []
    for l in locs:
        p = l.replace(ORIGIN, "") or "/"
        if any(p == s or p.startswith(s + "/") for s in SKIP_PREFIX):
            continue
        urls.append(l)
    if limit:
        urls = urls[:limit]
    print(f"[i] crawling {len(urls)} marketing pages", file=sys.stderr)

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for url, final_url, doc in ex.map(lambda u: fetch(u), urls):
            path = url.replace(ORIGIN, "") or "/"
            title, h1, copy = extract(url, final_url, doc)
            err = doc[7:120] if isinstance(doc, str) and doc.startswith("__ERR__") else ""
            rows.append({
                "页面链接": url,
                "标题": title or "",
                "页面": page_name(path),
                "内容类型": "首页文案" if path == "/" else page_name(path),
                "文案内容": copy or "",
                "status": "ERROR" if err else "OK",
                "error": err,
            })

    ok = [r for r in rows if r["status"] == "OK"]
    print(f"[i] ok={len(ok)} err={len(rows)-len(ok)}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "site_pages.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    print(f"[v] -> {OUT/'site_pages.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
