"""Rigaku（SmartLab など）の .ras。ヘッダーから走査の開始時刻と雰囲気温度を読む。

走査一本 = 一行。温度系列としての熱履歴は 1 ファイルからは分からないので、
台帳の thermal_history を series ごとに手で書く（gaps 列に出る）。
"""
from __future__ import annotations

import os
import re

from .common import parse_dt

DATE_FORMATS = ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S")


def header(path: str) -> dict:
    h = {}
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        for i, line in enumerate(f):
            if i > 400 or line.startswith("*RAS_INT_START"):
                break
            m = re.match(r'^\*(\S+)\s+"(.*)"\s*$', line.rstrip("\r\n"))
            if m:
                h[m.group(1)] = m.group(2)
    return h


def read(path: str):
    h = header(path)
    if not h:
        return None
    dt = parse_dt(h.get("MEAS_SCAN_START_TIME", ""), DATE_FORMATS)
    T = h.get("ATMOSPHERE_TEMP_START", "")
    try:
        T = "%g" % float(T)
    except ValueError:
        T = ""
    sample = h.get("FILE_SAMPLE", "") or os.path.splitext(os.path.basename(path))[0]
    return {
        "meas_id": "xrd-%s" % dt.strftime("%Y%m%d-%H%M%S") if dt else None,
        "instr": "xrd",
        "date": dt.strftime("%Y-%m-%d") if dt else "",
        "time": dt.strftime("%H:%M:%S") if dt else "",
        "sample": sample,
        "operator": h.get("FILE_OPERATOR", ""),
        "T_set_C": T,
        "format": "ras",
    }
