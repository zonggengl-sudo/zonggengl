#!/usr/bin/env python3
"""Fetch Shopify blog post publish dates.

Reads a blog sitemap, fetches each article, extracts JSON-LD
datePublished / dateModified, and writes a CSV + JSON dataset.

Usage:
    python3 fetch_shopify_blog_dates.py                      # kyniqo.com (default)
    python3 fetch_shopify_blog_dates.py shop.nexplayground.com
"""
import csv
import json
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "shopify"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# target store host (default: user's own KYNIQO store)
HOST = sys.argv[1] if len(sys.argv) > 1 else "kyniqo.com"
SLUG = HOST.split(".")[0].replace("shop", "nex").replace("-", "_")
if "nexplayground" in HOST:
    SLUG = "nexplayground"


def get(url, retries=2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == retries:
                return f"__ERR__{e}"
            time.sleep(1.5 * (i + 1))
    return "__ERR__"


def sitemap_path():
    return DATA / (f"sitemap_blogs_{SLUG}.xml"
                   if SLUG != "kyniqo" else "kyniqo_sitemap_blogs.xml")


def article_urls():
    xml = sitemap_path().read_text()
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    # keep only article pages (a blog handle + an article handle)
    out = []
    for l in locs:
        m = re.match(rf"https://{re.escape(HOST)}/blogs/([^/]+)/([^/?#]+)$", l)
        if m:
            out.append((m.group(1), m.group(2), l))
    return out


def parse(html):
    res = {"title": "", "published": "", "modified": ""}
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if m:
        res["published"] = m.group(1)
    m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    if m:
        res["modified"] = m.group(1)
    m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    if m:
        res["title"] = m.group(1)
    if not res["title"]:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            res["title"] = m.group(1).strip()
    return res


def main():
    arts = article_urls()
    print(f"[i] {len(arts)} articles found in sitemap", file=sys.stderr)
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(get, url): (blog, handle, url) for blog, handle, url in arts}
        for f in futs:
            blog, handle, url = futs[f]
            html = f.result()
            if html.startswith("__ERR__"):
                rows.append({"blog": blog, "handle": handle, "url": url,
                             "title": "", "published": "", "modified": "",
                             "status": "ERROR", "error": html[7:120]})
                continue
            d = parse(html)
            rows.append({"blog": blog, "handle": handle, "url": url,
                         "title": d["title"], "published": d["published"],
                         "modified": d["modified"], "status": "OK", "error": ""})

    rows.sort(key=lambda r: (r["published"] or "0000"), reverse=True)
    ok = sum(1 for r in rows if r["status"] == "OK")
    print(f"[i] ok={ok} err={len(rows)-ok}", file=sys.stderr)

    DATA.mkdir(parents=True, exist_ok=True)
    stem = f"blog_posts_dates_{SLUG}"
    with open(DATA / f"{stem}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["blog", "handle", "title", "published",
                                           "modified", "url", "status", "error"])
        w.writeheader()
        w.writerows(rows)
    (DATA / f"{stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[v] wrote {DATA/(stem+'.csv')}", file=sys.stderr)


if __name__ == "__main__":
    main()
