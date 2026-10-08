#!/usr/bin/env python3
"""自有站 Shopify 文章「增量核对」——零文章页请求版。

背景：kyniqo.com 已出现站点级 429 限流（"local_rate_limited"），逐篇抓 HTML
会大面积失败。本脚本改为**只读 sitemap** 与本地基线 CSV 比对：
  - 新增 / 下架文章（handle 级别）
  - sitemap lastmod 相对基线的变化
一次只需 0~1 个 HTTP 请求，彻底绕开限流。

用法:
    python3 tools/check_shopify_delta.py                  # 用缓存 sitemap 比对
    python3 tools/check_shopify_delta.py --fetch          # 先刷新 sitemap 再比对
    python3 tools/check_shopify_delta.py --json           # 机读输出
"""
import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "shopify"
HOST = "kyniqo.com"
SITEMAP = DATA / "kyniqo_sitemap_blogs.xml"
CSV = DATA / "blog_posts_dates_kyniqo.csv"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch_sitemap():
    """非破坏性刷新：仅当新 sitemap 的条目数 >= 现有缓存时才覆盖。

    坑（2026-10-07 实测）：kyniqo.com 的 `sitemap_blogs_1.xml` 返回的是
    **博客索引级**（仅 /blogs/news、/blogs/buying-guide、/blogs/active-play 三条），
    直接覆盖会把文章级缓存（33 条）打回 3 条，导致"全部下架"的假结论。
    """
    url = f"https://{HOST}/sitemap_blogs_1.xml"
    cur_n = len(re.findall(r"<loc>", SITEMAP.read_text(encoding="utf-8"))) if SITEMAP.exists() else 0
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
            n = len(re.findall(r"<loc>", body))
            if n >= cur_n and n > 0:
                SITEMAP.write_text(body, encoding="utf-8")
                print(f"[v] sitemap 已刷新 ({cur_n} -> {n}) -> {SITEMAP.name}")
                return True
            print(f"[!] 新 sitemap 仅 {n} 条 < 现有 {cur_n} 条（索引级 sitemap），"
                  f"已保留缓存不覆盖")
            return False
        except Exception as e:
            print(f"[!] sitemap 抓取失败({i+1}/4): {e}")
            time.sleep(4 * (2 ** i))
    return False


def parse_sitemap():
    xml = SITEMAP.read_text(encoding="utf-8")
    blocks = re.findall(r"<url>(.*?)</url>", xml, re.S)
    out = {}
    for b in blocks:
        loc = re.search(r"<loc>(.*?)</loc>", b)
        mod = re.search(r"<lastmod>(.*?)</lastmod>", b)
        if not loc:
            continue
        u = loc.group(1).strip()
        m = re.match(rf"https://{re.escape(HOST)}/blogs/([^/]+)/([^/?#]+)$", u)
        if not m:            # 跳过 /blogs/news 这类栏首页
            continue
        out[m.group(2)] = {"blog": m.group(1), "url": u,
                           "lastmod": mod.group(1).strip() if mod else ""}
    return out


def main():
    args = sys.argv[1:]
    if "--fetch" in args:
        fetch_sitemap()

    site = parse_sitemap()
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    base = {r["handle"]: r for r in rows if r.get("handle")}

    added = sorted(set(site) - set(base))
    removed = sorted(set(base) - set(site))
    changed = []
    for h in sorted(set(site) & set(base)):
        old_pub = (base[h].get("published") or "")[:10]
        new_lm = (site[h]["lastmod"] or "")[:10]
        if new_lm and old_pub and new_lm != old_pub:
            changed.append((h, old_pub, new_lm, site[h]["url"]))

    result = {"sitemap_articles": len(site), "baseline_articles": len(base),
              "added": [{"handle": h, **site[h]} for h in added],
              "removed": [{"handle": h, "url": base[h]["url"]} for h in removed],
              "lastmod_drift": [{"handle": h, "baseline_published": o, "sitemap_lastmod": n, "url": u}
                                for h, o, n, u in changed],
              "checked_at": datetime.now().isoformat(timespec="seconds")}

    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"sitemap 文章数: {len(site)}   基线 CSV 文章数: {len(base)}")
        print(f"新增文章: {len(added)}   下架文章: {len(removed)}   lastmod 漂移: {len(changed)}")
        if added:
            print("\n## 新增文章（需补登记发布时间）")
            for h in added:
                print(f"  + {site[h]['url']}   lastmod={site[h]['lastmod']}")
        if removed:
            print("\n## 下架文章")
            for h in removed:
                print(f"  - {base[h]['url']}")
        if changed:
            print("\n## lastmod 漂移（文章有更新，发布时间本身未变）")
            for h, o, n, u in changed:
                print(f"  ~ {h}: baseline={o} -> lastmod={n}")
        if not (added or removed or changed):
            print("\n[v] 无增量：文章集合与基线完全一致，发布时间数据可直接沿用。")

    out = DATA / f"shopify_delta_{datetime.now():%Y%m%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[v] -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
