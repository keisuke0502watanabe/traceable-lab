"""解析の見本: 台帳から DSC を選び、保持温度 Ta ごとに「結晶化の発熱ピークの時刻」と「融解ピーク温度」を並べる。

    python3 tools/example_analysis.py            # プロジェクト直下で
    python3 tools/example_analysis.py --sample ExampleFat-B

やっていること（どの解析でも同じ形）
  1. 台帳から行を選ぶ（status が bad のものは除く）
  2. analysis.new で解析フォルダを作る（問い・入力・手順・パラメータが manifest に残る）
  3. 計算して、図と表を A.out(...) に保存する。図の隅には ana_id を刻む
  4. A.finish で結果の要約と status を書く
  5. labkit refresh でギャラリーとビューアを更新する
"""
import argparse
import csv
import os
import subprocess
import sys

from labkit import analysis, ledger, svgplot
from labkit.readers.pyris_txt import read_table


def segments(prog_temp, time, tol=1e-6):
    """プログラム温度が一定の区間（等温保持）を (開始 index, 終了 index) で返す。"""
    out, i, n = [], 0, len(prog_temp)
    while i < n - 1:
        j = i
        while j + 1 < n and abs(prog_temp[j + 1] - prog_temp[i]) < tol:
            j += 1
        if j - i >= 5:
            out.append((i, j))
        i = j + 1
    return out


def analyse_run(path):
    cols, rows = read_table(path)
    t = [r[0] for r in rows]
    hf = [r[-1] for r in rows]
    Tp = [r[3] for r in rows]
    holds = segments(Tp, t)
    if len(holds) < 2:
        return None
    a, b = holds[-1]                       # 最後の保持 = Ta
    skip = a + 10                          # 保持直後の装置の過渡（約 1 分）を避ける
    k = min(range(skip, b + 1), key=lambda i: hf[i])
    t_peak = t[k] - t[a]
    heat = list(range(b + 1, len(rows)))   # 最後の昇温
    m = max(heat, key=lambda i: hf[i]) if heat else None
    return {
        "Ta": round(Tp[a], 2),
        "t_cryst_peak_min": round(t_peak, 2),
        "Tm_peak_C": round(Tp[m], 2) if m is not None else None,
        "heating": ([Tp[i] for i in heat], [hf[i] for i in heat]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="ExampleFat-A")
    a = ap.parse_args()

    L = ledger.load()
    rows = L.select(instr="dsc", sample=a.sample, status=lambda s: s != "bad")
    if not rows:
        sys.exit("台帳に %s の DSC がありません" % a.sample)
    A = analysis.new(
        L, "%s-ta-scan" % a.sample.lower(),
        question="%s: 保持温度 Ta が結晶化の速さと融解温度をどう決めるか" % a.sample,
        inputs=rows, procedure="tools/example_analysis.py",
        params={"hold_skip_min": 1.0, "peak": "heat-flow extremum"})

    res = []
    for r in rows:
        out = analyse_run(L.resolve(r))
        if out:
            res.append((r, out))
    res.sort(key=lambda x: x[1]["Ta"])

    with open(A.out("per_run.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["meas_id", "Ta_C", "t_cryst_peak_min", "Tm_peak_C"])
        for r, o in res:
            w.writerow([r["meas_id"], o["Ta"], o["t_cryst_peak_min"], o["Tm_peak_C"]])

    stamp = "%s · labkit" % A.ana_id
    svgplot.plot(A.out("t_peak_vs_Ta.svg"),
                 [{"x": [o["Ta"] for _, o in res], "y": [o["t_cryst_peak_min"] for _, o in res]}],
                 xlabel="Ta (°C)", ylabel="結晶化ピークまでの時間 (min)",
                 title="%s: Ta と結晶化の速さ" % a.sample, stamp=stamp, markers=True)
    svgplot.plot(A.out("Tm_vs_Ta.svg"),
                 [{"x": [o["Ta"] for _, o in res], "y": [o["Tm_peak_C"] for _, o in res]}],
                 xlabel="Ta (°C)", ylabel="融解ピーク温度 (°C)",
                 title="%s: Ta と融解温度" % a.sample, stamp=stamp, markers=True)
    svgplot.plot(A.out("heating_curves.svg"),
                 [{"x": o["heating"][0], "y": o["heating"][1], "label": "Ta %g °C" % o["Ta"]} for _, o in res],
                 xlabel="温度 (°C)", ylabel="熱流 (mW, 吸熱が上)",
                 title="%s: 最後の昇温" % a.sample, stamp=stamp)

    A.finish(results={"n_runs": len(res),
                      "Tm_range_C": [min(o["Tm_peak_C"] for _, o in res), max(o["Tm_peak_C"] for _, o in res)]},
             status="used")
    with open(A.notes_path, "a", encoding="utf-8") as f:
        f.write("\n## 結果の表\n`out/per_run.csv`（%d ラン）\n" % len(res))
    print(A.ana_id, "->", A.dir)
    subprocess.run([sys.executable, "-m", "labkit", "refresh", "--root", L.root], check=False)


if __name__ == "__main__":
    main()
