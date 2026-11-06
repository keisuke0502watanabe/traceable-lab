"""Fig. 1 の見本。解析フォルダの CSV を読んで、論文用の図を out/ に書く。

    python3 figs/fig01_example.py ana-YYYYMMDD-...      # 原稿フォルダの直下で
"""
import csv
import os
import sys

from labkit import svgplot

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def main():
    if len(sys.argv) < 2:
        sys.exit("使い方: python3 figs/fig01_example.py <ana_id>")
    ana_id = sys.argv[1]
    src = os.path.join(PROJECT, "analyses", ana_id, "out", "per_run.csv")
    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    svgplot.plot(os.path.join(HERE, "out", "fig01_example.svg"),
                 [{"x": [float(r["Ta_C"]) for r in rows], "y": [float(r["Tm_peak_C"]) for r in rows]}],
                 xlabel="Ta (°C)", ylabel="Tm (°C)", stamp="Fig. 1 · " + ana_id, markers=True)
    print("-> figs/out/fig01_example.svg")


if __name__ == "__main__":
    main()
