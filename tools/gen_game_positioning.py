#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_game_positioning.py — Nex Playground 游戏定位矩阵（纯本地、免 Apify Key）

从 data/nex_playground/site_pages.json 的 62 款游戏详情页正文中提取：
  - 玩家人数区间（1 Player / 1 to 2 players / 1 to 4 players ...）
  - 品类标签（Action Adventure / Party / Arcade / Sports / Preschool ...）
  - H1 标题（players+品类之后的第一句主标题），并判定是「产品名直述」还是「口号式」

产出 output/游戏定位矩阵_<date>.md（+ .json）

用法：
    python3 tools/gen_game_positioning.py [--date YYYY-MM-DD]

注意（历史踩坑）：
  - site_pages.json 全中文键：页面链接 / 标题 / 页面 / 内容类型 / 文案内容
  - 竞品标题含管道符 "XXX | Nex Playground"，写 markdown 表格前必须 split("|")[0]
  - 游戏页「内容类型」值是「游戏」，/games 目录页也是「游戏」→ 用 /games/ 路径过滤
"""
import json
import os
import re
import sys
import collections
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "nex_playground", "site_pages.json")
OUT_DIR = os.path.join(ROOT, "output")

# 品类词表：长词优先，避免 'Action' 截断 'Action Adventure'
CATEGORIES = [
    # 长词必须排在短词之前，否则 'Action' 会截断 'Action Adventure'、
    # 'Party' 会截断 'Party Games'（踩坑：曾导致 H1 残留 ' Games' / '& Dance' 噪声）
    "Action Adventure", "Party Games", "Family Fun", "Brain Boost",
    "Fitness & Training", "Music & Dance", "Fun Center",
    "Preschool", "Arcade", "Sports", "Puzzle", "Cozy", "NexPets", "NexGym",
    "Family", "Brain", "Fitness", "Music", "Party", "Action",
]

PLAYERS_RE = re.compile(r"(\d+)\s*(?:\s*to\s*(\d+))?\s*players?\b", re.I)
CAT_RE = re.compile(r"players?\s+(" + "|".join(re.escape(c) for c in CATEGORIES) + r")\b", re.I)


def load_pages():
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    games = [p for p in data
             if p.get("内容类型") == "游戏" and "/games/" in str(p.get("页面链接", ""))]
    return data, games


def parse_game(page):
    url = str(page.get("页面链接", ""))
    title = str(page.get("标题", "")).split("|")[0].strip()
    text = str(page.get("文案内容", "")).replace("\n", " ").strip()

    m = PLAYERS_RE.search(text)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    players = f"{lo}-{hi}"

    cm = CAT_RE.search(text)
    category = cm.group(1).strip() if cm else "未识别"

    # H1：从「品类词结束」处起，到 " on Nex Playground" / " Unlock with" 之前
    # （踩坑：若从 players 结束处起，会把品类词误并入 H1，如 'Adventure Aeon Guard'）
    start = cm.end() if cm else m.end()
    h1 = ""
    rest = text[start:].strip()
    sm = re.match(r"(.{3,120}?)\s+(?:on Nex Playground|Unlock with|exclusively with)", rest)
    if sm:
        h1 = sm.group(1).strip()
    if not h1:
        h1 = rest[:80].strip()
    # 折叠连续重复词（竞品模板会把游戏名重复 4 次，如 'Active Arcade Active Arcade ...'）
    words = h1.split()
    dedup = []
    for w in words:
        if len(dedup) >= 2 and dedup[-1] == w and dedup[-2] == w:
            continue
        dedup.append(w)
    h1 = " ".join(dedup)

    # 标题风格：以 slug 词集为「产品名」基准，算与 H1 的词级重合率
    # （踩坑：不能用 SEO title 全文，它带 ': Active Adventure Game' 之类后缀，
    #   且 'Avatar: The Last Airbender' 冒号分割会截断 → 必须用 slug 词集）
    def toks(s):
        return set(w for w in re.split(r"[^a-z0-9]+", s.lower()) if len(w) > 2)

    slug = url.rstrip("/").split("/")[-1]
    base = toks(slug) | toks(title.split(":")[0])
    h1t = toks(h1)
    if not h1 or not h1t:
        style = "未知"
    else:
        overlap = len(base & h1t) / max(len(h1t), 1)
        style = "产品名直述" if overlap >= 0.5 else "口号式"

    return {
        "url": url,
        "slug": url.rstrip("/").split("/")[-1],
        "title": title,
        "players": players,
        "players_min": lo,
        "players_max": hi,
        "category": category,
        "h1": h1,
        "style": style,
    }


def main():
    date = None
    if "--date" in sys.argv:
        i = sys.argv.index("--date")
        if i + 1 < len(sys.argv):
            date = sys.argv[i + 1]
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    if date == "today":
        date = datetime.now().strftime("%Y-%m-%d")

    data, games = load_pages()
    rows = []
    for p in games:
        r = parse_game(p)
        if r:
            rows.append(r)

    by_players = collections.Counter(r["players"] for r in rows)
    by_cat = collections.Counter(r["category"] for r in rows)
    by_style = collections.Counter(r["style"] for r in rows)

    # 交叉：品类 × 是否支持 3+ 人
    multi = collections.Counter()
    for r in rows:
        if r["players_max"] >= 3:
            multi[r["category"]] += 1

    L = []
    L.append(f"# Nex Playground 游戏定位矩阵 {date}")
    L.append("")
    L.append(f"- 数据源：`data/nex_playground/site_pages.json`（全站 {len(data)} 页）")
    L.append(f"- 游戏详情页：**{len(games)}**，成功解析：**{len(rows)}**")
    L.append("- 提取维度：正文首段模板 `<N> Player(s) <品类> <H1> on Nex Playground`")
    L.append("")

    L.append("## 1. 玩家人数分布")
    L.append("")
    L.append("| 人数区间 | 游戏数 | 占比 | 场景解读 |")
    L.append("|---|---:|---:|---|")
    scene = {"1-1": "单人练习/闯关", "1-2": "亲子或双人对战", "1-3": "小家庭",
             "1-4": "全家/派对同乐", "1-6": "大型聚会"}
    for k, v in sorted(by_players.items(), key=lambda x: -x[1]):
        L.append(f"| {k} | {v} | {v*100//max(len(rows),1)}% | {scene.get(k,'')} |")
    L.append("")

    L.append("## 2. 品类分布")
    L.append("")
    L.append("| 品类 | 游戏数 | 占比 | 其中支持3人+ |")
    L.append("|---|---:|---:|---:|")
    for k, v in by_cat.most_common():
        L.append(f"| {k} | {v} | {v*100//max(len(rows),1)}% | {multi.get(k,0)} |")
    L.append("")

    L.append("## 3. H1 标题风格")
    L.append("")
    L.append("| 风格 | 数量 | 说明 |")
    L.append("|---|---:|---|")
    L.append(f"| 产品名直述 | {by_style.get('产品名直述',0)} | H1 直接用游戏名，SEO 友好 |")
    L.append(f"| 口号式 | {by_style.get('口号式',0)} | H1 用行动口号/双关，品牌调性优先 |")
    if by_style.get("未知", 0):
        L.append(f"| 未知 | {by_style.get('未知',0)} | 模板未匹配 |")
    L.append("")
    slogan = [r for r in rows if r["style"] == "口号式"]
    if slogan:
        L.append("### 口号式标题清单（竞品在打磨转化文案的位置）")
        L.append("")
        L.append("| 游戏 | 品类 | 人数 | H1 |")
        L.append("|---|---|---|---|")
        for r in sorted(slogan, key=lambda x: x["title"]):
            L.append(f"| {r['title']} | {r['category']} | {r['players']} | {r['h1']} |")
        L.append("")

    L.append("## 4. 全量明细")
    L.append("")
    L.append("| # | 游戏 | 品类 | 人数 | H1 | 风格 |")
    L.append("|---:|---|---|---|---|---|")
    for i, r in enumerate(sorted(rows, key=lambda x: (-x["players_max"], x["category"], x["title"])), 1):
        L.append(f"| {i} | {r['title']} | {r['category']} | {r['players']} | {r['h1']} | {r['style']} |")
    L.append("")

    md = "\n".join(L)
    os.makedirs(OUT_DIR, exist_ok=True)
    md_path = os.path.join(OUT_DIR, f"游戏定位矩阵_{date}.md")
    js_path = os.path.join(OUT_DIR, f"游戏定位矩阵_{date}.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "games": len(games), "parsed": len(rows),
                   "by_players": dict(by_players), "by_category": dict(by_cat),
                   "by_style": dict(by_style), "rows": rows}, f,
                  ensure_ascii=False, indent=2)
    print(f"[v] -> {md_path}  ({len(L)} lines, parsed={len(rows)}/{len(games)})")
    print(f"[v] -> {js_path}")


if __name__ == "__main__":
    main()
