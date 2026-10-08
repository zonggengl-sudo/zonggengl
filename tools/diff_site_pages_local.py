#!/usr/bin/env python3
"""本地差分：对比两份 site_pages.json（或爬虫快照），输出逐段 diff。

用途：当飞书不可读（如 OAuth 过期）时，仍能用「上次抓取 vs 本次抓取」
产出竞品变更情报，不依赖任何外部服务。

用法:
    python3 tools/diff_site_pages_local.py                     # 自动取最新两份
    python3 tools/diff_site_pages_local.py OLD.json NEW.json
    python3 tools/diff_site_pages_local.py OLD.json NEW.json --out data/nex_playground/drift_diff_<date>.txt

输出：
    1) stdout 汇总（新增页/删除页/变更页数、变更页 top-N）
    2) 写入 diff 文件（默认 data/nex_playground/drift_diff_<YYYYMMDD>.txt）
"""
import json
import sys
import re
import difflib
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "nex_playground"


def norm_url(u: str) -> str:
    u = (u or "").strip().rstrip("/")
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u


def load(path: Path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict):  # 兼容 {url: {...}} 结构
        rows = [{"页面链接": k, **v} if isinstance(v, dict) else {"页面链接": k, "文案内容": v}
                for k, v in d.items()]
    else:
        rows = d
    out = {}
    for r in rows:
        out[norm_url(r.get("页面链接", ""))] = r
    return out


def strip_noise(text: str) -> str:
    """剥离易造成假 drift 的噪声：行首列表编号、多余空白。"""
    lines = []
    for ln in (text or "").splitlines():
        ln = re.sub(r"^\s*\d+\.\s*", "", ln)   # 行首 "1. "
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_arg = None
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            out_arg = sys.argv[i + 1]

    if len(args) >= 2:
        old_p, new_p = Path(args[0]), Path(args[1])
    else:
        cands = sorted(DATA.glob("site_pages*.json"), key=lambda p: p.stat().st_mtime)
        cands = [p for p in cands if p.name != "site_pages.json"] + \
                ([DATA / "site_pages.json"] if (DATA / "site_pages.json").exists() else [])
        if len(cands) < 2:
            print("[x] 找不到两份可对比的 site_pages 快照")
            return 1
        old_p, new_p = cands[-2], cands[-1]

    old, new = load(old_p), load(new_p)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for k in sorted(set(old) & set(new)):
        a = strip_noise(old[k].get("文案内容", ""))
        b = strip_noise(new[k].get("文案内容", ""))
        if a != b:
            changed.append((k, old[k].get("文案内容", ""), new[k].get("文案内容", "")))

    changed.sort(key=lambda x: abs(len(x[2]) - len(x[1])), reverse=True)

    stamp = datetime.now().strftime("%Y%m%d")
    out_path = Path(out_arg) if out_arg else DATA / f"drift_diff_{stamp}.txt"

    buf = []
    buf.append(f"# Nex Playground 独立站本地差分 {datetime.now():%Y-%m-%d %H:%M}")
    buf.append(f"OLD: {old_p.name}  ({len(old)} 页)")
    buf.append(f"NEW: {new_p.name}  ({len(new)} 页)")
    buf.append("")
    buf.append(f"新增页: {len(added)}   删除页: {len(removed)}   内容变更页: {len(changed)}")
    buf.append("")
    if added:
        buf.append("## 新增页面")
        buf += [f"+ {u}" for u in added]
        buf.append("")
    if removed:
        buf.append("## 删除页面")
        buf += [f"- {u}" for u in removed]
        buf.append("")

    buf.append("## 内容变更（按字符数变化绝对值降序）")
    buf.append("")
    for k, a, b in changed:
        title = new[k].get("标题", "")
        o = strip_noise(a).splitlines()
        n = strip_noise(b).splitlines()
        buf.append(f"### {k}  [{new[k].get('内容类型','')}] {title}")
        buf.append(f"字符数: {len(a)} -> {len(b)}  ({len(b)-len(a):+d})")
        sm = difflib.SequenceMatcher(None, o, n)
        hits = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            hits += 1
            buf.append(f"  [{tag}]")
            for x in o[i1:i2]:
                buf.append(f"    - {x[:220]}")
            for x in n[j1:j2]:
                buf.append(f"    + {x[:220]}")
            if hits > 40:
                buf.append("  ...(截断，变更过多)")
                break
        if hits == 0:
            buf.append("  (仅空白/编号差异，已归一)")
        buf.append("")

    out_path.write_text("\n".join(buf), encoding="utf-8")

    print(f"OLD={old_p.name}({len(old)}) NEW={new_p.name}({len(new)})")
    print(f"新增={len(added)} 删除={len(removed)} 变更={len(changed)}")
    for k, a, b in changed[:12]:
        print(f"  {len(b)-len(a):+6d}  {k}")
    print(f"[v] -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
