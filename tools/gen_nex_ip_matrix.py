#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_nex_ip_matrix.py — 竞品 Nex Playground 授权 IP 全景矩阵

纯本地读取 data/nex_playground/site_pages.json（免 Apify Key、免网络），
把 62 款游戏按「第三方授权 IP / 自有原创 IP / 通用玩法类」三档归类，
输出 output/nex_授权IP矩阵_<date>.md。

用途：
  - 一眼看清竞品的 IP 护城河结构：哪些是花钱买的有版权壁垒，哪些是可被抄的通用玩法。
  - 每晚差分若有新增游戏，会体现在本矩阵中（新增页 -> 自动进入清单）。

用法:
  python3 tools/gen_nex_ip_matrix.py [--date YYYY-MM-DD]
"""
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "nex_playground", "site_pages.json")
OUTDIR = os.path.join(ROOT, "output")

# slug 前缀/关键字 -> (展示名, 版权方, 档位)
# 档位: A=第三方授权IP(有壁垒)  B=自有原创IP  C=通用玩法/无版权
IP_RULES = [
    (r"^avatar-the-last-airbender", "Avatar: The Last Airbender", "Nickelodeon / Paramount", "A"),
    (r"^barbie-", "Barbie", "Mattel", "A"),
    (r"^bluey-", "Bluey", "BBC Studios / Disney", "A"),
    (r"^care-bears-", "Care Bears", "Cloudco Entertainment", "A"),
    (r"^candy-land", "Candy Land", "Hasbro", "A"),
    (r"^connect-4-", "Connect 4", "Hasbro", "A"),
    (r"^cookie-monster|^elmo-", "Sesame Street (Cookie Monster / Elmo)", "Sesame Workshop", "A"),
    (r"^dora-", "Dora the Explorer", "Nickelodeon / Paramount", "A"),
    (r"^dude-perfect-", "Dude Perfect", "Dude Perfect (YouTube 顶流)", "A"),
    (r"^gabbys-dollhouse", "Gabby's Dollhouse", "DreamWorks / Nickelodeon", "A"),
    (r"^how-to-train-your-dragon", "How to Train Your Dragon", "DreamWorks", "A"),
    (r"^hungry-hungry-hippos", "Hungry Hungry Hippos", "Hasbro", "A"),
    (r"^kung-fu-panda", "Kung Fu Panda", "DreamWorks", "A"),
    (r"^miraculous-", "Miraculous Ladybug", "ZAG / Toei", "A"),
    (r"^nfl-", "NFL", "NFL 职业橄榄球联盟", "A"),
    (r"^nhl-", "NHL", "NHL 职业冰球联盟", "A"),
    (r"^nickelodeon-", "Nickelodeon (The Tiny Chef Show)", "Nickelodeon / Paramount", "A"),
    (r"^peppa-pig-", "Peppa Pig", "Hasbro / eOne", "A"),
    (r"^rubiks-", "Rubik's Cube", "Spin Master", "A"),
    (r"^teenage-mutant-ninja-turtles", "Teenage Mutant Ninja Turtles (TMNT)", "Nickelodeon / Paramount", "A"),
    (r"^unicorn-academy", "Unicorn Academy", "Netflix / Spin Master", "A"),
    (r"^fruit-ninja", "Fruit Ninja", "Halfbrick Studios", "A"),
    (r"^zumba-", "Zumba", "Zumba Fitness LLC", "A"),
    # 自有 / 原创 IP
    (r"^starri$|^starri-", "Starri", "Nex 自有吉祥物 IP", "B"),
    (r"^boxflow-", "BoxFlow", "Nex 自研健身", "B"),
    (r"^nexgym", "NexGym", "Nex 自研健身", "B"),
    (r"^nexpets-", "NexPets", "Nex 自研", "B"),
    (r"^pips-tale", "Pip's Tale", "Nex 自研", "B"),
    (r"^miniacs-", "Miniacs", "Nex 自研", "B"),
    (r"^tumbobots", "Tumbobots", "Nex 自研", "B"),
    (r"^scanny|^brainy-inc", "Scanny / Brainy Inc.", "Nex 自研", "B"),
]

TIER_NAME = {"A": "第三方授权 IP（有版权壁垒）", "B": "自有原创 IP", "C": "通用玩法 / 无版权"}


def slug_of(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def classify(slug: str):
    for pat, name, owner, tier in IP_RULES:
        if re.match(pat, slug):
            return name, owner, tier
    return None, None, "C"


def main():
    date = None
    if "--date" in sys.argv:
        i = sys.argv.index("--date")
        if i + 1 < len(sys.argv):
            date = sys.argv[i + 1]
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(SRC):
        print(f"[x] 找不到 {SRC}，请先跑 tools/crawl_nex_site.py")
        return 1

    with open(SRC, encoding="utf-8") as f:
        pages = json.load(f)

    game_pages = [
        p for p in pages
        if "/games/" in p.get("页面链接", "") and p.get("status") == "OK"
    ]
    slugs = sorted({slug_of(p["页面链接"]) for p in game_pages if slug_of(p["页面链接"])})

    buckets = OrderedDict((t, []) for t in ("A", "B", "C"))
    for s in slugs:
        name, owner, tier = classify(s)
        buckets[tier].append((s, name or s, owner or "—"))

    # 按版权方聚合 A 档
    owner_map = OrderedDict()
    for s, name, owner in buckets["A"]:
        owner_map.setdefault(owner, []).append(name)

    lines = []
    lines.append(f"# Nex Playground — 授权 IP 全景矩阵（{date}）")
    lines.append("")
    lines.append(f"> 数据源：`data/nex_playground/site_pages.json`（本地，免 Key）")
    lines.append(f"> 游戏详情页总数：**{len(slugs)}** ｜ 生成脚本：`tools/gen_nex_ip_matrix.py`")
    lines.append("")
    lines.append("## 一、结构总览")
    lines.append("")
    lines.append("| 档位 | 含义 | 游戏数 | 占比 |")
    lines.append("|---|---|---:|---:|")
    for t in ("A", "B", "C"):
        n = len(buckets[t])
        lines.append(f"| {t} | {TIER_NAME[t]} | {n} | {n * 100 // max(len(slugs), 1)}% |")
    lines.append("")
    lines.append("**读法**：A 档是竞品花钱买来的护城河（不可直接复制）；B 档是其自有资产；")
    lines.append("C 档是通用玩法，任何体感厂商都能做，不构成差异化。")
    lines.append("")
    lines.append("## 二、A 档：第三方授权 IP（按版权方聚合）")
    lines.append("")
    lines.append("| 版权方 | IP 数 | 具体 IP |")
    lines.append("|---|---:|---|")
    for owner, names in sorted(owner_map.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"| {owner} | {len(names)} | {', '.join(sorted(set(names)))} |")
    lines.append("")
    lines.append(f"**授权 IP 覆盖 {len(owner_map)} 家版权方 / {len(buckets['A'])} 款游戏。**")
    lines.append("")
    lines.append("## 三、B 档：自有原创 IP")
    lines.append("")
    lines.append("| 游戏 slug | IP | 归属 |")
    lines.append("|---|---|---|")
    for s, name, owner in buckets["B"]:
        lines.append(f"| `{s}` | {name} | {owner} |")
    lines.append("")
    lines.append("## 四、C 档：通用玩法 / 无版权（可被复制）")
    lines.append("")
    lines.append("| 游戏 slug |")
    lines.append("|---|")
    for s, name, owner in buckets["C"]:
        lines.append(f"| `{s}` |")
    lines.append("")
    lines.append("## 五、结论提示")
    lines.append("")
    a, b, c = len(buckets["A"]), len(buckets["B"]), len(buckets["C"])
    lines.append(f"- 竞品 **{a}/{len(slugs)}** 的游戏依赖外部授权，IP 采购是其核心壁垒，")
    lines.append("  也是其最大成本项与谈判风险点（授权到期即下架）。")
    lines.append(f"- 自有 IP 仅 **{b}** 款，占比 {b * 100 // max(len(slugs), 1)}%，自研能力相对薄弱。")
    lines.append(f"- 通用玩法 **{c}** 款，无法阻挡同质化竞争。")
    lines.append("")

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"nex_授权IP矩阵_{date}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[v] -> {out}  ({len(lines)} lines, games={len(slugs)}, A={a} B={b} C={c})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
