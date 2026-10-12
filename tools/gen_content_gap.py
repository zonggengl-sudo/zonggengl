#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容缺口分析：自有站 kyniqo.com 博客 vs 竞品 Nex Playground 游戏/IP 覆盖度

目的：
  竞品有 62 款游戏（含 25 款第三方授权 IP）。自有站 30 篇博客是 SEO 主战场。
  本脚本回答两个问题：
    Q1【覆盖缺口】竞品哪些高热度游戏/IP，自有站博客一篇都没写？→ 可切入的选题
    Q2【防御缺口】竞品哪些内容角度（订阅/价格/隐私/年龄）自有站还没覆盖？→ 差异化

用法：
  python3 tools/gen_content_gap.py            # 输出到 output/内容缺口分析_<date>.md
  python3 tools/gen_content_gap.py --json     # 额外输出 json

纯本地、免 Key、无需网络。
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

# 竞品内容角度关键词（自有站博客应防御性覆盖的议题）
ANGLES = [
    ("订阅/付费模式", ["play pass", "subscription", "subscribe", "monthly", "annual", "会员", "订阅"]),
    ("价格/成本", ["price", "cost", "$", "pricing", "价格", "多少钱"]),
    ("隐私/摄像头安全", ["privacy", "camera", "安全", "隐私", "data"]),
    ("年龄段/适龄", ["age", "ages", "toddler", "preschool", "teen", "年龄", "几岁"]),
    ("空间/场地需求", ["space", "room", "small room", "空间", "客厅"]),
    ("替代品/对比", ["alternative", "vs ", "versus", "compare", "对比", "替代"]),
    ("礼品/送礼场景", ["gift", "christmas", "birthday", "holiday", "礼物", "圣诞"]),
    ("多人/家庭同玩", ["multiplayer", "family", "together", "party", "多人", "家庭", "一起玩"]),
]


def load_blog():
    """返回 [(title, handle, url, published)]"""
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
    pages = d if isinstance(d, list) else list(d.values())
    out = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        # 注意：正文字段是中文键「文案内容」，不是 text/content
        out.append({
            "url": p.get("页面链接") or "",
            "title": p.get("标题") or "",
            "page": p.get("页面") or "",
            "type": p.get("内容类型") or "",
            "text": p.get("文案内容") or "",
        })
    return out


def slug_words(s):
    """把 slug / 标题拆成有意义的小写词袋"""
    s = re.sub(r"&(nbsp|ndash|mdash);?", " ", s.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    stop = {"the", "a", "an", "of", "for", "to", "and", "in", "on", "with", "is", "are",
            "how", "what", "why", "best", "your", "you", "kids", "kid", "com", "https",
            "www", "blogs", "news", "blog", "html", "kyniqo", "ndash"}
    return {w for w in s.split() if len(w) > 2 and w not in stop}


def main():
    as_json = "--json" in sys.argv
    today = datetime.now().strftime("%Y-%m-%d")

    blogs = load_blog()
    pages = load_pages()
    if not blogs or not pages:
        print("[x] 数据不足，退出")
        return 1

    blog_blob = " ".join(b["title"] + " " + b["handle"] for b in blogs).lower()
    blog_words = slug_words(blog_blob)

    games = [p for p in pages if (p["type"] or "") == "游戏" and "/games/" in p["url"]]
    # 去重（同 URL 只留一个）
    seen, uniq_games = set(), []
    for g in games:
        if g["url"] in seen:
            continue
        seen.add(g["url"])
        uniq_games.append(g)

    covered, gap = [], []
    for g in uniq_games:
        slug = g["url"].rstrip("/").split("/games/")[-1]
        words = slug_words(slug + " " + g["title"])
        if not words:
            continue
        # 命中率： slug 词有多少出现在自有站博客词袋里
        hit = words & blog_words
        ratio = len(hit) / len(words)
        raw = (g["title"] or slug.replace("-", " ")).strip()
        # 竞品 title 形如 "XXX | Nex Playground"，管道符会撑破 markdown 表格
        name = raw.split("|")[0].strip().replace("|", "/") or slug.replace("-", " ")
        rec = {"name": name, "slug": slug, "url": g["url"], "ratio": round(ratio, 2),
               "match": sorted(hit)[:5]}
        (covered if ratio >= 0.5 else gap).append(rec)

    covered.sort(key=lambda x: -x["ratio"])
    gap.sort(key=lambda x: x["ratio"], reverse=False)

    # Q2 角度防御缺口
    angle_rows = []
    for label, kws in ANGLES:
        n_blog = sum(1 for b in blogs if any(k in (b["title"] + " " + b["handle"]).lower() for k in kws))
        angle_rows.append({"角度": label, "自有站篇数": n_blog})
    angle_rows.sort(key=lambda x: x["自有站篇数"])

    # ---------- 输出 ----------
    lines = []
    A = lines.append
    A(f"# 内容缺口分析：kyniqo.com 博客 vs Nex Playground（{today}）\n")
    A("> 生成脚本：`tools/gen_content_gap.py`（纯本地、免 Key、无需网络）")
    A("> 数据源：自有站 `data/shopify/blog_posts_dates_kyniqo.csv`（30 篇 OK）")
    A("> 　　　　竞品站 `data/nex_playground/site_pages.json`（83 页 / 62 款游戏）\n")
    A("## 1. 结论速览\n")
    A(f"- 自有站博客：**{len(blogs)} 篇**（OK 状态）")
    A(f"- 竞品游戏详情独立页：**{len(uniq_games)} 款**")
    A(f"- 已被自有站博客覆盖（关键词命中率 ≥50%）：**{len(covered)} 款**")
    A(f"- **内容缺口（未覆盖）：{len(gap)} 款** ← 这些是可以直接开题的 SEO 选题\n")

    A("## 2. 内容缺口清单（竞品有独立页、自有站未覆盖）\n")
    A("| # | 竞品游戏 / IP | 命中率 | 建议动作 |")
    A("|---|---|---|---|")
    for i, g in enumerate(gap, 1):
        if g["ratio"] < 0.30:
            action = "🔴 开新文（对比/评测向）"
        elif g["ratio"] < 0.40:
            action = "🟠 开新文（或大幅扩写）"
        else:
            action = "🟡 在现有文中补一节内链"
        A(f"| {i} | {g['name']} | {g['ratio']} | {action} |")
    A("")
    A("<details><summary>缺口 URL 明细</summary>\n")
    for g in gap:
        A(f"- {g['url']}")
    A("\n</details>\n")

    A("## 3. 已覆盖（对照组，无需重复投入）\n")
    A("| 竞品游戏 / IP | 命中率 | 匹配到的自有站关键词 |")
    A("|---|---|---|")
    for g in covered[:20]:
        A(f"| {g['name']} | {g['ratio']} | {', '.join(g['match']) or '—'} |")
    if len(covered) > 20:
        A(f"\n（共 {len(covered)} 款，仅列前 20）")
    A("")

    A("## 4. 议题防御缺口（自有站博客角度覆盖度）\n")
    A("| 议题角度 | 自有站篇数 | 状态 |")
    A("|---|---|---|")
    for r in angle_rows:
        st = "🔴 空白" if r["自有站篇数"] == 0 else ("🟡 偏薄" if r["自有站篇数"] <= 2 else "🟢 尚可")
        A(f"| {r['角度']} | {r['自有站篇数']} | {st} |")
    A("")

    A("## 5. 可执行的下一步\n")
    top = gap[:8]
    if top:
        A("**优先级最高的 8 个选题**（竞品已有独立页承接流量，自有站零覆盖）：\n")
        for i, g in enumerate(top, 1):
            A(f"{i}. 《{g['name']}》— 竞品页 {g['url']}")
        A("")
    A("> 说明：命中率基于 slug + 标题词袋与自有站博客词袋的交集占比，")
    A("> 是**选题线索**而非精确语义匹配，开题前仍需人工判断搜索意图。\n")

    os.makedirs(OUT, exist_ok=True)
    md_path = os.path.join(OUT, f"内容缺口分析_{today}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[v] -> {md_path}  ({len(lines)} lines, gap={len(gap)} covered={len(covered)})")

    if as_json:
        jp = os.path.join(OUT, f"内容缺口分析_{today}.json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump({"date": today, "blogs": len(blogs), "games": len(uniq_games),
                       "gap": gap, "covered": covered, "angles": angle_rows},
                      f, ensure_ascii=False, indent=2)
        print(f"[v] -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
