"""PerkinElmer Pyris（DSC）のテキスト書き出し。

ヘッダーの Data Collected から測定日時、Sample Weight から質量、Method Steps から熱履歴を起こす::

    1)  Heat from 25.00°C to 80.00°C at 15.00°C/min   →  25→80@15
    2)  Hold for 15.0 min at 80.00°C                   →  hold80/15min

Data Collected の日付は装置の地域設定で日/月/年 か 月/日/年 になる。既定は日/月/年を先に試す。
"""
from __future__ import annotations

import ntpath
import re

from .common import fmt_num, parse_dt, thermal_history_ta

STEP_RE = re.compile(
    r"^\s*\d+\)\s*(Heat|Cool)\s+from\s+(-?[\d.]+)\S*\s+to\s+(-?[\d.]+)\S*\s+at\s+(-?[\d.]+)\S*/min", re.I)
HOLD_RE = re.compile(r"^\s*\d+\)\s*Hold\s+for\s+([\d.]+)\s*min\s+at\s+(-?[\d.]+)", re.I)
HEADER_KEYS = ("Filename", "Operator ID", "Sample ID", "Data Collected", "Sample Weight", "Comment")
DATE_FORMATS = ("%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S")


def parse_header(path: str):
    """(ヘッダーの dict, 熱履歴の段の list, データ表が始まる行番号) を返す。"""
    hdr, steps, start = {}, [], None
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        for i, line in enumerate(f):
            if i > 400:
                break
            line = line.rstrip("\r\n")
            m = STEP_RE.match(line)
            if m:
                _, a, b, r = m.groups()
                steps.append("%s→%s@%s" % (fmt_num(a), fmt_num(b), fmt_num(r)))
                continue
            m = HOLD_RE.match(line)
            if m:
                mins, T = m.groups()
                steps.append("hold%s/%smin" % (fmt_num(T), fmt_num(mins)))
                continue
            if ":" in line and not line.startswith("\t"):
                k, _, v = line.partition(":")
                k = k.strip()
                if k in HEADER_KEYS and k not in hdr:
                    hdr[k] = v.strip()
            if line.strip().startswith("1)") and "Scan" in line:
                start = i
                break
    return hdr, steps, start


def read(path: str):
    hdr, steps, _ = parse_header(path)
    if "Data Collected" not in hdr:
        return None
    dt = parse_dt(hdr["Data Collected"], DATE_FORMATS)
    m = re.search(r"([\d.]+)\s*mg", hdr.get("Sample Weight", ""))
    sample = re.sub(r"\s+", " ", hdr.get("Sample ID", "")).strip()
    return {
        "meas_id": "dsc-%s" % dt.strftime("%Y%m%d-%H%M%S") if dt else None,
        "instr": "dsc",
        "date": dt.strftime("%Y-%m-%d") if dt else "",
        "time": dt.strftime("%H:%M:%S") if dt else "",
        "sample": sample,
        "mass_mg": m.group(1) if m else "",
        "operator": hdr.get("Operator ID", "").strip(),
        "thermal_history": " > ".join(steps),
        "Ta_C": thermal_history_ta(steps),
        "format": "pyris-txt",
        # 同じ測定のコピー: 装置側のファイル名と測定日時が同じなら同一
        "_dup_key": "pyris|%s|%s" % (ntpath.basename(hdr.get("Filename", "")).lower(), hdr["Data Collected"]),
    }


def read_table(path: str):
    """データ表を読む。列名の list と、行（float の list）の list を返す。

    Pyris の列は通常 Time / Unsubtracted Heat Flow / Baseline Heat Flow / Program Temperature /
    Sample Temperature / ... / Heat Flow。列名は 2 行に分かれているので繋げて返す。
    """
    _, _, start = parse_header(path)
    cols, rows = [], []
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        lines = f.read().splitlines()
    if start is None:
        return cols, rows
    h1 = [c.strip() for c in lines[start + 1].split("\t")]
    h2 = [c.strip() for c in lines[start + 2].split("\t")] if start + 2 < len(lines) else []
    h2 += [""] * (len(h1) - len(h2))
    cols = [(" ".join(x for x in (a, b) if x)) for a, b in zip(h1, h2)]
    for line in lines[start + 3:]:
        parts = line.split("\t")
        try:
            vals = [float(p) for p in parts if p.strip()]
        except ValueError:
            continue
        if vals:
            rows.append(vals)
    cols = [c for c in cols if c]
    return cols, rows
