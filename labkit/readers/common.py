"""reader が共通で使う小道具。"""
from __future__ import annotations

from datetime import datetime


def fmt_num(x) -> str:
    """15.00 → '15'、-0.00 → '0'。"""
    return "%g" % (float(x) + 0.0)


def parse_dt(text: str, formats) -> datetime | None:
    text = (text or "").strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def thermal_history_ta(steps: list[str]) -> str:
    """冷却のあとに来る最長の等温保持を Ta とみなす（目安。信用しすぎない）。

    steps は 'A→B@rate' / 'holdT/Nmin' の列。
    """
    best = None
    seen_cool = False
    for s in steps:
        if "→" in s:
            a, rest = s.split("→", 1)
            b = rest.split("@")[0]
            try:
                if float(b) < float(a):
                    seen_cool = True
            except ValueError:
                pass
        elif s.startswith("hold") and seen_cool and "/" in s:
            T, mins = s[4:].split("/", 1)
            try:
                m = float(mins.replace("min", ""))
            except ValueError:
                continue
            if best is None or m > best[1]:
                best = (T, m)
    return best[0] if best else ""
