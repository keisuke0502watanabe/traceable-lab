"""matplotlib が無くても図を出せる、最小限の SVG 折れ線・散布図。

図の右下に出どころ（ana_id など）を小さく刻む。図だけが一人歩きしても解析に戻れるようにするため。
本格的な図は matplotlib などで描き、同じように脚注を入れるとよい。
"""
from __future__ import annotations

import html
import math

PALETTE = ["#1462a8", "#b8452a", "#2f8f6b", "#8a5cb8", "#c28a1a", "#4a7f8c", "#a33c6e", "#5a6b72"]


def _ticks(lo: float, hi: float, n: int = 6):
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    out, v = [], start
    while v <= hi + 1e-9 * step:
        out.append(round(v, 10))
        v += step
    return out


def plot(path: str, series: list[dict], xlabel: str = "", ylabel: str = "", title: str = "",
         stamp: str = "", width: int = 640, height: int = 420, markers: bool = False, lines: bool = True):
    """series: [{"x": [...], "y": [...], "label": "..."}]。SVG を path に書く。"""
    xs = [x for s in series for x in s["x"]]
    ys = [y for s in series for y in s["y"]]
    if not xs:
        xs, ys = [0, 1], [0, 1]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad_y = (y1 - y0) * 0.06 or 1
    y0, y1 = y0 - pad_y, y1 + pad_y
    L, R, T, B = 70, 20 + (130 if len(series) > 1 else 0), 40, 62
    W, H = width - L - R, height - T - B

    def sx(x):
        return L + (x - x0) / ((x1 - x0) or 1) * W

    def sy(y):
        return T + H - (y - y0) / ((y1 - y0) or 1) * H

    e = html.escape
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
           'font-family="Helvetica,Arial,sans-serif" font-size="12">' % (width, height, width, height),
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    if title:
        out.append('<text x="%d" y="24" font-size="14" font-weight="bold" fill="#16232a">%s</text>' % (L, e(title)))
    for t in _ticks(x0, x1):
        X = sx(t)
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#e3e9e7"/>' % (X, T, X, T + H))
        out.append('<text x="%.1f" y="%d" text-anchor="middle" fill="#56676e">%g</text>' % (X, T + H + 16, t))
    for t in _ticks(y0, y1):
        Y = sy(t)
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e3e9e7"/>' % (L, Y, L + W, Y))
        out.append('<text x="%d" y="%.1f" text-anchor="end" fill="#56676e">%g</text>' % (L - 6, Y + 4, t))
    out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#56676e"/>' % (L, T, W, H))
    out.append('<text x="%d" y="%d" text-anchor="middle" fill="#16232a">%s</text>' % (L + W / 2, T + H + 36, e(xlabel)))
    out.append('<text transform="translate(18 %d) rotate(-90)" text-anchor="middle" fill="#16232a">%s</text>' % (T + H / 2, e(ylabel)))
    for i, s in enumerate(series):
        c = s.get("color") or PALETTE[i % len(PALETTE)]
        pts = " ".join("%.1f,%.1f" % (sx(x), sy(y)) for x, y in zip(s["x"], s["y"]))
        if lines and len(s["x"]) > 1:
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6"/>' % (pts, c))
        if markers:
            for x, y in zip(s["x"], s["y"]):
                out.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (sx(x), sy(y), c))
        if len(series) > 1:
            ly = T + 8 + i * 18
            out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>' % (L + W + 12, ly, L + W + 30, ly, c))
            out.append('<text x="%d" y="%d" fill="#16232a">%s</text>' % (L + W + 36, ly + 4, e(s.get("label", ""))))
    if stamp:
        out.append('<text x="%d" y="%d" text-anchor="end" font-size="9.5" fill="#8a9a9f">%s</text>' % (width - 6, height - 6, e(stamp)))
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path
