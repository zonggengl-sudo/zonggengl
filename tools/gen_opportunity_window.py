#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机会窗口追踪：竞品「有 IP 但无落地页」× 自有站「有博客覆盖吗」的交叉矩阵

背景（2026-10-13 建立）：
  竞品 nexplayground.com 会把新签下的 IP 先写进 13+ 个游戏页与 /games 聚合页做曝光，
  但**不一定立刻建 /games/<slug> 独立落地页**。这个时间差就是 SEO 机会窗口：
    - 竞品无独立页 → 该 IP 词的搜索结果页没有竞品权威落地页压制 → kyniqo.com 可抢布局
    - 竞品一旦建页 → 窗口关闭
  典型案例：Sonic Forces: Rival Rush（SEGA 顶级 IP）
    10-07 首次出现在 14 个页面，至今（10-13）/games/sonic* 独立页**仍为 0** → 窗口开启第 7 天。

四维判定：
  A 窗口开启且我方空白  → 🔴 最高优先：立刻写
  B 窗口开启但我方已覆盖 → 🟢 卡位成功：守住
  C 窗口关闭且我方空白  → 🟠 硬碰硬：需差异化角度
  D 窗口关闭且我方已覆盖 → ⚪ 维持

用法：
  python3 tools/gen_opportunity_window.py            # md
  python3 tools/gen_opportunity_window.py --json     # md + json

纯本地、免 Key、无需网络、约 2 秒。
"""
import csv
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")

BLOG_CSV = os.path.join(DATA, "shopify", "blog_posts_dates_kyniqo.csv")
SITE_PAGES = os.path.join(DATA, "nex_playground", "site_pages.json")

# 重点盯梢的 IP（**slug 片段** -> 显示名）。
# 🚨 2026-10-13 踩坑：frag 必须能匹配竞品真实 slug，不能写品牌名。
#    反例：写 "sesame" 会漏掉 elmo-says / elmo-abbys-magical-letter-hunt 两个既有落地页，
#    把「窗口已关闭」误判成「窗口开启」。已改回 "elmo"。新增条目前先核对 62 个真实 slug。
WATCH = [
    ("sonic", "Sonic the Hedgehog (SEGA)"),
    ("elmo", "Elmo / Sesame Workshop"),
    ("cookie-monster", "Cookie Monster / Sesame Workshop"),
    ("peppa-pig", "Peppa Pig"),
    ("dora", "Dora the Explorer"),
    ("nickelodeon", "Nickelodeon / Tiny Chef"),
    ("teenage-mutant-ninja-turtles", "TMNT 忍者神龟"),
    ("avatar", "Avatar: The Last Airbender"),
    ("how-to-train-your-dragon", "How to Train Your Dragon"),
    ("kung-fu-panda", "Kung Fu Panda"),
    ("care-bears", "Care Bears"),
    ("miraculous", "Miraculous Ladybug"),
    ("unicorn-academy", "Unicorn Academy"),
    ("gabby", "Gabby's Dollhouse"),
    ("bluey", "Bluey"),
    ("barbie", "Barbie"),
    ("paw-patrol", "Paw Patrol"),
    ("hot-wheels", "Hot Wheels"),
    ("minecraft", "Minecraft"),
    ("marvel", "Marvel"),
    ("star-wars", "Star Wars"),
    ("disney", "Disney"),
]


def load_blog():
    rows = []
    if not os.path.exists(BLOG_CSV):
        print(f"[x] 找不到自有站博客 CSV: {BLOG_CSV}")
        return rows
    with open(BLOG_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status") != "OK":
                continue
            rows.append({
                "title": (r.get("title") or "").replace("\n", " ").strip(),
                "handle": r.get("handle") or "",
                "url": r.get("url") or "",
                "published": (r.get("published") or "")[:10],
            })
    return rows


def load_pages():
    if not os.path.exists(SITE_PAGES):
        print(f"[x] 找不到竞品页数据: {SITE_PAGES}")
        return []
    with open(SITE_PAGES, encoding="utf-8") as f:
        d = json.load(f)
    return d if isinstance(d, list) else list(d.values())


def page_url(p):
    return (p.get("url") or p.get("页面链接") or "").strip()


def page_text(p):
    return (p.get("content") or p.get("文案内容") or "") + " " + (p.get("title") or p.get("标题") or "")


def game_slug(url):
    m = re.search(r"/games/([a-z0-9\-]+)", url or "")
    return m.group(1) if m else ""


def slug_words(s):
    """与 gen_content_gap.py 保持一致的词袋切分"""
    s = re.sub(r"&(nbsp|ndash|mdash);?", " ", (s or "").lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    stop = {"the", "a", "an", "of", "for", "to", "and", "in", "on", "with", "is", "are",
            "how", "what", "why", "best", "your", "you", "kids", "kid", "com", "https",
            "www", "blogs", "news", "blog", "html", "kyniqo", "ndash"}
    return {w for w in s.split() if len(w) > 2 and w not in stop}


def main():
    want_json = "--json" in sys.argv
    date = datetime.now().strftime("%Y-%m-%d")

    pages = load_pages()
    blogs = load_blog()
    if not pages:
        return 1

    game_pages = [p for p in pages if game_slug(page_url(p))]
    standalone = {game_slug(page_url(p)) for p in game_pages}
    # 全站提及：所有页面正文里出现过该关键词
    all_text = [page_text(p).lower() for p in pages]

    blog_blob = " ".join(b["title"] + " " + b["handle"] for b in blogs).lower()
    blog_words = slug_words(blog_blob)

    rows = []
    for frag, display in WATCH:
        frag_l = frag.lower()
        # 竞品独立落地页
        has_standalone = any(frag_l in s for s in standalone)
        # 竞品提及页数（正文里是空格形式 "Kung Fu Panda"，slug 里才是连字符，两种都要试）
        variants = {frag_l, frag_l.replace("-", " ")}
        mention_pages = sum(1 for t in all_text if any(v in t for v in variants))
        # 我方博客覆盖（与 gen_content_gap.py 一致：词袋重合率 >= 0.5）
        ip_words = slug_words(display + " " + frag.replace("-", " "))
        if ip_words:
            hit = ip_words & blog_words
            ratio = len(hit) / len(ip_words)
        else:
            hit, ratio = set(), 0.0
        covered_us = ratio >= 0.5
        our_hits = [b for b in blogs
                    if any(w in (b["title"] + " " + b["handle"]).lower() for w in ip_words)]

        if mention_pages == 0 and not has_standalone:
            # 竞品根本没碰这个 IP：无竞争信号，属自选动作，不算「窗口」
            q, prio = "E", "⚪ 无信号（竞品未涉及）"
        elif not has_standalone and not covered_us:
            q, prio = "A", "🔴 最高优先（窗口开启）"
        elif not has_standalone and covered_us:
            q, prio = "B", "🟢 卡位成功（守住）"
        elif has_standalone and not covered_us:
            q, prio = "C", "🟠 硬碰硬（需差异化）"
        else:
            q, prio = "D", "⚪ 维持（已正面覆盖）"

        rows.append({
            "ip": display, "frag": frag,
            "competitor_standalone": has_standalone,
            "competitor_mentions": mention_pages,
            "our_blog_posts": len(our_hits),
            "our_cover_ratio": round(ratio, 2),
            "quadrant": q, "priority": prio,
            "our_urls": [b["url"] for b in our_hits][:3],
        })

    order = {"A": 0, "C": 1, "B": 2, "D": 3, "E": 4}
    rows.sort(key=lambda r: (order[r["quadrant"]], -r["competitor_mentions"]))

    L = []
    L.append(f"# 机会窗口追踪（{date}）")
    L.append("")
    L.append("> 竞品「有 IP 提及但无独立落地页」= SEO 窗口开启；与自有站博客覆盖交叉，得四象限优先级。")
    L.append("> 纯本地差分，免 API Key。")
    L.append("")
    L.append("## 1. 四象限总览")
    L.append("")
    L.append("| 象限 | 含义 | 数量 | 动作 |")
    L.append("|------|------|------|------|")
    for q, name, act in [
        ("A", "窗口开启 + 我方空白", "🔴 立刻写，抢在竞品建落地页前占住词"),
        ("B", "窗口开启 + 我方已覆盖", "🟢 卡位成功，守住并持续加厚"),
        ("C", "窗口关闭 + 我方空白", "🟠 竞品已有权威落地页，需差异化角度切入"),
        ("D", "窗口关闭 + 我方已覆盖", "⚪ 维持现状"),
        ("E", "竞品未涉及", "⚪ 无竞争信号，自选动作，低优先"),
    ]:
        L.append(f"| {q} | {name} | {sum(1 for r in rows if r['quadrant'] == q)} | {act} |")
    L.append("")
    L.append("## 2. 明细矩阵")
    L.append("")
    L.append("| IP | 竞品独立页 | 竞品提及页数 | 我方覆盖度 | 象限 | 优先级 |")
    L.append("|----|-----------|-------------|-----------|------|--------|")
    for r in rows:
        sa = "有" if r["competitor_standalone"] else "**无**"
        L.append(f"| {r['ip']} | {sa} | {r['competitor_mentions']} | {r['our_cover_ratio']:.0%} "
                 f"| {r['quadrant']} | {r['priority']} |")
    L.append("")

    a_rows = [r for r in rows if r["quadrant"] == "A"]
    L.append("## 3. 🔴 立即行动清单（象限 A）")
    L.append("")
    if a_rows:
        for r in a_rows:
            L.append(f"- **{r['ip']}**：竞品已在 {r['competitor_mentions']} 个页面曝光但**未建独立落地页**，"
                     f"自有站 0 篇覆盖 → 建议尽快上线对应 SEO 文章。")
    else:
        L.append("- 无（所有盯梢 IP 均已处理）")
    L.append("")
    L.append("> ⚠️ 合规提醒：第三方授权 IP 属他人商标/版权，自有站内容应走"
             "「玩法介绍 / 选购指南 / 对比测评」等资讯角度，避免使用官方 Logo 或暗示官方授权。")
    L.append("")

    md_path = os.path.join(OUT, f"机会窗口追踪_{date}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[v] -> {md_path}  ({len(L)} lines, A={len(a_rows)}/{len(rows)})")

    if want_json:
        jp = os.path.join(OUT, f"机会窗口追踪_{date}.json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump({"date": date, "rows": rows}, f, ensure_ascii=False, indent=2)
        print(f"[v] -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
