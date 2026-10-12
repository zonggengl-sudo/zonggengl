#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞品内容版图演进分析（纯本地 / 免 API Key）

背景：nexplayground.com 自 2026-09-26 起页面 URL 集合恒为 83 页（无增删），
但快照字节数持续增长（221667 -> 224560 -> 225981），说明竞品在持续**改写文案**。
本脚本对比两个快照的「文案内容」，量化：
  1. 哪些页面被改写、改写幅度（字符数增减）
  2. 按「内容类型」聚合的投入分布 -> 反推竞品近期内容重心
  3. Top 扩写页面 -> 竞品正在主推什么

用法：
  python3 tools/gen_content_evolution.py [OLD.json] [NEW.json]
  默认 OLD=data/nex_playground/site_pages_20260926_morning.json
       NEW=data/nex_playground/site_pages.json
产出：
  output/内容演进分析_<date>.md
  output/内容演进分析_<date>.json
"""
import io
import json
import os
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "nex_playground")
OUT = os.path.join(ROOT, "output")

# 实质性改写阈值（字符）。
# 实测：竞品全站共用的导航/页脚/促销条等模板模块一有变动，
# 会让 83 个页面"同时变化" ±1 / ±21 字符。这类是**模板噪声**，不是文案重写。
# 只有超过该阈值才认定为「竞品真的在改这个页面的内容」。
SUBSTANTIAL = 100

OLD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "site_pages_20260926_morning.json")
NEW = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "site_pages.json")


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    """归一化：压缩空白，去掉纯噪声（数字编号等）"""
    s = s or ""
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_title(t):
    """竞品 title 含管道符 'XXX | Nex Playground'，塞表格前必须剥离"""
    t = t or ""
    return t.split("|")[0].strip()


def main():
    old = load(OLD)
    new = load(NEW)
    om = {x.get("页面链接"): x for x in old}
    nm = {x.get("页面链接"): x for x in new}

    added = sorted(set(nm) - set(om))
    removed = sorted(set(om) - set(nm))
    common = sorted(set(om) & set(nm))

    changed = []
    for u in common:
        ot = norm(om[u].get("文案内容"))
        nt = norm(nm[u].get("文案内容"))
        if ot != nt:
            changed.append({
                "url": u,
                "title": clean_title(nm[u].get("标题")),
                "page": nm[u].get("页面"),
                "type": nm[u].get("内容类型") or "(未分类)",
                "old_len": len(ot),
                "new_len": len(nt),
                "delta": len(nt) - len(ot),
            })

    changed.sort(key=lambda r: -r["delta"])

    # 区分「实质改写」与「模板级微变」
    subst = [r for r in changed if abs(r["delta"]) >= SUBSTANTIAL]
    noise = [r for r in changed if abs(r["delta"]) < SUBSTANTIAL]

    # 按内容类型聚合（只统计实质改写，避免模板噪声污染投入判断）
    by_type = {}
    for r in subst:
        t = r["type"]
        by_type.setdefault(t, {"n": 0, "delta": 0})
        by_type[t]["n"] += 1
        by_type[t]["delta"] += r["delta"]
    by_type = sorted(by_type.items(), key=lambda kv: -kv[1]["delta"])

    total_old = sum(len(norm(x.get("文案内容"))) for x in old)
    total_new = sum(len(norm(x.get("文案内容"))) for x in new)

    date = datetime.now().strftime("%Y-%m-%d")
    md_path = os.path.join(OUT, f"内容演进分析_{date}.md")
    js_path = os.path.join(OUT, f"内容演进分析_{date}.json")

    L = []
    L.append(f"# 竞品内容版图演进分析（{date}）\n")
    L.append(f"> 基线 `{os.path.basename(OLD)}` → 当前 `{os.path.basename(NEW)}`")
    L.append(f"> 纯本地差分，免 API Key。页面 URL 集合恒定 83 页，本文本衡量**文案改写投入**。\n")

    L.append("## 1. 总量\n")
    L.append("| 指标 | 基线 | 当前 | 变化 |")
    L.append("|------|------|------|------|")
    L.append(f"| 页面数 | {len(old)} | {len(new)} | {len(new)-len(old):+d} |")
    L.append(f"| 文案总字符 | {total_old:,} | {total_new:,} | {total_new-total_old:+,} |")
    L.append(f"| 新增页面 | — | — | {len(added)} |")
    L.append(f"| 下架页面 | — | — | {len(removed)} |")
    L.append(f"| 文案有变动的页面 | — | — | {len(changed)} |")
    L.append(f"| **其中：实质改写（≥{SUBSTANTIAL} 字符）** | — | — | **{len(subst)}** |")
    L.append(f"| 其中：模板级微变（<{SUBSTANTIAL} 字符） | — | — | {len(noise)} |")
    L.append("")
    L.append(f"> ⚠️ **读法提醒**：竞品 83 个页面共用导航/页脚/促销条等模板模块，"
             f"模板一改动会让全站页面同时变动 ±1~±21 字符，属**模板噪声**，不代表该页被重写。"
             f"下文所有投入判断只基于 **{len(subst)} 个实质改写页面**。\n")

    if added:
        L.append("### 新增页面\n")
        for u in added:
            L.append(f"- `{u}` — {clean_title(nm[u].get('标题'))}")
        L.append("")
    if removed:
        L.append("### 下架页面\n")
        for u in removed:
            L.append(f"- `{u}` — {clean_title(om[u].get('标题'))}")
        L.append("")

    L.append("## 2. 内容重心：实质改写投入按类型分布\n")
    L.append("> 字符数净增越多 = 竞品把文案精力投在这里（已剔除模板噪声）。\n")
    L.append("| 内容类型 | 实质改写页数 | 字符净增 | 解读 |")
    L.append("|----------|-------------|---------|------|")
    if by_type:
        for t, v in by_type[:15]:
            tag = "🔴 主投" if v["delta"] >= 500 else ("🟡 次要" if v["delta"] > 0 else "🟢 收缩")
            L.append(f"| {t} | {v['n']} | {v['delta']:+,} | {tag} |")
    else:
        L.append("| （无实质改写） | 0 | 0 | — |")
    L.append("")

    L.append("## 3. Top 扩写页面（竞品正在主推）\n")
    L.append("| # | 标题 | 类型 | 字符变化 |")
    L.append("|---|------|------|---------|")
    n_top = 0
    for i, r in enumerate(subst, 1):
        if r["delta"] <= 0:
            break
        n_top += 1
        L.append(f"| {n_top} | {r['title'][:40]} | {r['type']} | {r['old_len']:,} → {r['new_len']:,} ({r['delta']:+,}) |")
    if n_top == 0:
        L.append("| — | 本区间无实质扩写页面 | — | — |")
    L.append("")

    shrink = [r for r in subst if r["delta"] < 0]
    if shrink:
        L.append("## 4. 实质缩写的页面（竞品在弱化）\n")
        L.append("| 标题 | 类型 | 字符变化 |")
        L.append("|------|------|---------|")
        for r in sorted(shrink, key=lambda x: x["delta"])[:10]:
            L.append(f"| {r['title'][:40]} | {r['type']} | {r['old_len']:,} → {r['new_len']:,} ({r['delta']:+,}) |")
        L.append("")

    L.append("## 5. 结论\n")
    if not subst:
        L.append(f"- 本区间**无实质改写**：{len(changed)} 个页面的变动全部落在 ±{SUBSTANTIAL} 字符以内，"
                 f"判定为站点级模板模块（导航/页脚/促销条）同步变动，**竞品内容无实质动作**。\n")
    else:
        top = by_type[0][0] if by_type else "—"
        grow = sum(1 for r in subst if r["delta"] > 0)
        L.append(f"- 竞品在区间内**实质改写 {len(subst)} 个页面**（其中 {grow} 个扩写），"
                 f"总字符 {total_old:,} → {total_new:,}（{total_new-total_old:+,}）。")
        L.append(f"- 投入最重的类型：**{top}**，是竞品当前内容主战场。")
        L.append(f"- 另有 {len(noise)} 个页面仅发生 <{SUBSTANTIAL} 字符的模板级微变，不计入投入判断。")
        L.append("- 页面数恒定说明竞品**不做页面扩张、只做存量页精修**——"
                 "靠反复打磨既有页提升转化/排名，而非靠新增页覆盖长尾。")
        L.append("- 对我方启示：与其广铺页面，不如对高价值页做深度内容迭代；"
                 "竞品重投的商业化页面（订阅/购买/线下渠道）是其变现命脉，值得逐字对标。\n")

    # ---- 第 6 节：Top 扩写页面的新增文案摘取（句子级 diff）----
    L.append("## 6. 主投页面新增文案摘取\n")
    L.append("> 对实质扩写 Top 页面做句子级 diff，看竞品**具体加了什么**（而非只看到字符数变化）。\n")
    if subst:
        for r in [x for x in subst if x["delta"] > 0][:3]:
            u = r["url"]
            ot = norm(om[u].get("文案内容") if u in om else "")
            nt = norm(nm[u].get("文案内容"))
            L.append(f"### {r['title']}  (+{r['delta']:,} 字符)\n")
            sm = SequenceMatcher(None, ot.split(". "), nt.split(". "))
            got = 0
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("insert", "replace") and j2 > j1:
                    seg = ". ".join(nt.split(". ")[j1:j2]).strip()
                    if len(seg) > 25:
                        # 去掉标题里可能的管道符，避免撑破表格/列表
                        seg = re.sub(r"\s*\|\s*", " - ", seg)
                        L.append(f"- {seg[:400]}")
                        got += 1
                        if got >= 8:
                            break
            if got == 0:
                L.append("- （无足够长度的新增句子）")
            L.append("")
    else:
        L.append("- 本区间无实质扩写页面，无新增文案可摘取。\n")

    md = "\n".join(L)
    with io.open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with io.open(js_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date, "old": os.path.basename(OLD), "new": os.path.basename(NEW),
            "pages_old": len(old), "pages_new": len(new),
            "added": added, "removed": removed,
            "total_chars_old": total_old, "total_chars_new": total_new,
            "changed": changed,
            "substantial_threshold": SUBSTANTIAL,
            "substantial": subst, "template_noise": noise,
            "by_type": [{"type": k, **v} for k, v in by_type],
        }, f, ensure_ascii=False, indent=2)

    print(f"[v] -> {md_path}  ({len(L)} lines, changed={len(changed)})")
    print(f"[v] -> {js_path}")


if __name__ == "__main__":
    main()
