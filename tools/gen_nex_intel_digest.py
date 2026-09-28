#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 data/nex_playground/site_pages.json（竞品站爬取结果）生成结构化竞品情报摘要。

用法:
    python3 tools/gen_nex_intel_digest.py [--date YYYY-MM-DD]

产出:
    output/nex_竞品情报摘要_<date>.md

说明:
    - 只读取本地已爬取数据，不联网、不依赖 Apify。
    - 抽取维度: 页面类型分布 / 定价订阅 / Play Pass 限定游戏 / IP 合作 /
      商业与售后政策 / 游戏库清单。
"""
import argparse
import collections
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "nex_playground", "site_pages.json")
OUTDIR = os.path.join(ROOT, "output")

# 关注的合作 IP / 品牌关键词
IP_KEYWORDS = [
    "Bluey", "Sesame Street", "Rubik", "Disney", "Marvel", "Nickelodeon",
    "Paw Patrol", "Peppa", "Barbie", "Hot Wheels", "UNO", "Mattel",
    "Avatar", "Teenage Mutant", "Miraculous", "Care Bears", "SpongeBob",
    "Transformers", "Squishmallows",
]
# 竞品自有 IP / 自有产品线（区别于外部授权）
FIRST_PARTY = ["Starri", "Boxflow", "NexGym", "NexPets"]
# 政策类关键词 -> 用于抽取政策原文行
POLICY_PATTERNS = {
    "退款/取消": r"refund|cancel",
    "多主机授权": r"more than one Nex Playground|maximum of 2|multiple Play Pass",
    "激活码时效": r"activation code|code delivery",
    "礼品赠送": r"as a gift|gift",
    "第三方渠道": r"Amazon|retailer",
}


def load_pages():
    with open(SRC, encoding="utf-8") as f:
        return json.load(f)


def extract_prices(pages):
    """返回 {价格串: {'count':n, 'urls':[...]}}"""
    hits = {}
    for p in pages:
        text = p.get("文案内容", "") or ""
        url = p.get("页面链接", "")
        for m in re.findall(r"\$\s?\d[\d,]*(?:\.\d{2})?", text):
            key = m.replace(" ", "")
            hits.setdefault(key, {"count": 0, "urls": []})
            hits[key]["count"] += 1
            if url not in hits[key]["urls"]:
                hits[key]["urls"].append(url)
    return dict(sorted(hits.items(), key=lambda kv: -kv[1]["count"]))


def extract_policy_lines(pages):
    """按主题抽取政策相关原文行（去重、截断）。"""
    out = collections.defaultdict(list)
    seen = set()
    for p in pages:
        text = p.get("文案内容", "") or ""
        for theme, pat in POLICY_PATTERNS.items():
            for line in text.split("\n"):
                line = line.strip()
                if not line or len(line) < 25:
                    continue
                if re.search(pat, line, re.I):
                    key = (theme, line[:80])
                    if key in seen:
                        continue
                    seen.add(key)
                    out[theme].append(line[:300])
    return out


def extract_ip_mentions(pages):
    out = collections.defaultdict(list)
    for p in pages:
        text = p.get("文案内容", "") or ""
        title = p.get("标题", "") or ""
        for ip in IP_KEYWORDS:
            if re.search(re.escape(ip), text, re.I) or re.search(re.escape(ip), title, re.I):
                out[ip].append(p.get("页面链接", ""))
    return out


# Play Pass 限定的严格表述（避免命中页脚/导航里的通用 "Play Pass" 字样）
PASS_EXCLUSIVE_RE = re.compile(
    r"(?:available|exclusively|playable)\s+(?:only\s+)?(?:on|with|via)\s+"
    r"(?:Nex\s+Playground\s*)?(?:\+\s*|with\s*|,\s*)?Play\s+Pass",
    re.I,
)


def extract_pass_exclusives(games, head_chars=1200):
    """识别 Play Pass 限定 / 独占游戏。

    只看正文前 head_chars 个字符（页眉/卖点区），避开页脚导航里的通用 Play Pass 链接，
    否则会把全部游戏误判为限定。
    """
    res = []
    for p in games:
        text = (p.get("文案内容", "") or "")[:head_chars]
        if PASS_EXCLUSIVE_RE.search(text):
            res.append((p.get("标题", ""), p.get("页面链接", "")))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    pages = load_pages()
    games = [p for p in pages if p.get("内容类型") == "游戏"]
    # 游戏目录索引页本身不是单个游戏，排除
    games = [p for p in games if p.get("页面链接", "").rstrip("/").endswith("/games") is False]

    by_type = collections.Counter(p.get("内容类型", "?") for p in pages)
    prices = extract_prices(pages)
    policies = extract_policy_lines(pages)
    ips = extract_ip_mentions(pages)
    exclusives = extract_pass_exclusives(games)

    L = []
    A = L.append
    A(f"# Nex Playground 竞品站内容情报摘要（{args.date}）\n")
    A(f"> 数据源：`data/nex_playground/site_pages.json`（自研爬虫，免 Apify Key）  ")
    A(f"> 生成脚本：`tools/gen_nex_intel_digest.py`  ")
    A(f"> 竞品站：https://www.nexplayground.com ／自有站为 kyniqo.com，请勿混淆\n")

    A("## 1. 概览\n")
    A(f"- 抓取页面总数：**{len(pages)}**")
    A(f"- 游戏详情页：**{len(games)}**")
    A(f"- 页面类型数：{len(by_type)}\n")

    A("## 2. 页面类型分布\n")
    A("| 内容类型 | 页面数 |")
    A("|---|---|")
    for k, v in by_type.most_common():
        A(f"| {k} | {v} |")

    A("\n## 3. 定价与订阅情报\n")
    if prices:
        A("| 价格 | 出现次数 | 出现页面（前2） |")
        A("|---|---|---|")
        for k, v in prices.items():
            urls = "、".join(f"`{u}`" for u in v["urls"][:2])
            A(f"| {k} | {v['count']} | {urls} |")
    else:
        A("_本轮未扫描到价格信息_")
    A("\n- Play Pass 为订阅制内容服务；官网主打 **Play Pass 限定游戏** 作为付费转化点。")
    A("- 站点明确宣传 `60+ games`（游戏库规模）。")

    A("\n## 4. Play Pass 限定 / 独占游戏\n")
    A("> 口径：仅统计页面**卖点区**（正文前 1200 字符）明确写出 "
      "「available / exclusively on Play Pass」的页面，属**保守下界**；"
      "页脚导航中的通用 Play Pass 链接不计入。\n")
    if exclusives:
        A(f"共识别 **{len(exclusives)}** 个：\n")
        for t, u in exclusives:
            name = re.sub(r"\s*\|\s*Nex Playground\s*$", "", t).strip()
            A(f"- [{name}]({u})")
    else:
        A("_未识别到明确限定表述_")

    A("\n## 5. IP / 联名合作线索\n")
    A("### 5.1 外部授权 IP\n")
    if ips:
        A("| IP / 品牌 | 提及页面数 |")
        A("|---|---|")
        for ip, urls in sorted(ips.items(), key=lambda kv: -len(kv[1])):
            A(f"| {ip} | {len(urls)} |")
    else:
        A("_未识别到已知 IP_")
    A("\n### 5.2 竞品自有 IP / 自有产品线\n")
    fp = {}
    for brand in FIRST_PARTY:
        n = sum(
            1 for p in pages
            if re.search(re.escape(brand), (p.get("文案内容", "") or "") + (p.get("标题", "") or ""), re.I)
        )
        if n:
            fp[brand] = n
    if fp:
        A("| 自有 IP | 提及页面数 |")
        A("|---|---|")
        for k, v in sorted(fp.items(), key=lambda kv: -kv[1]):
            A(f"| {k} | {v} |")
    else:
        A("_未识别_")

    A("\n## 6. 商业与售后政策（原文摘录）\n")
    for theme in POLICY_PATTERNS:
        lines = policies.get(theme, [])
        if not lines:
            continue
        A(f"**{theme}**\n")
        for ln in lines[:6]:
            A(f"- {ln}")
        A("")

    A("\n## 7. 游戏库清单\n")
    A(f"共 {len(games)} 个游戏详情页：\n")
    for p in sorted(games, key=lambda x: (x.get("标题", "") or "")):
        t = p.get("标题", "") or ""
        name = re.sub(r"\s*\|\s*Nex Playground\s*$", "", t).strip()
        A(f"- [{name}]({p.get('页面链接','')})")

    A("\n---\n")
    A(f"_生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"nex_竞品情报摘要_{args.date}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[v] -> {out}  ({len(L)} lines, games={len(games)}, types={len(by_type)})")


if __name__ == "__main__":
    main()
