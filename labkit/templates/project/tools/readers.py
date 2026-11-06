"""このプロジェクト専用の reader（測定ファイル → 台帳の一行）。

labkit に入っている reader（Pyris の .txt、Rigaku の .ras）より先に、ここの READERS が試される。
自分の装置の形式を足すときは、関数を書いて READERS に (拡張子の集合, 関数) を足す。

reader の約束
- ファイル 1 本を受け取り、台帳の 1 行（dict）を返す。読めないファイルには None
- meas_id はファイルの中身（測定日時・走査番号）から決める。ファイル名から決めない
- 返せるキー: meas_id, instr, date, time, sample, mass_mg, operator, thermal_history,
  Ta_C, T_set_C, format, session, series（ほかのキーは台帳の列として足される）
- 同じ測定のコピーを見分けたいときは _dup_key を返す（省略するとファイル内容の一致で判定）
"""
import csv
import os
from datetime import datetime


def read_two_column_csv(path):
    """例: 1 行目が '# sample=…; date=2025-06-13 14:39:01; T=48' のような 2 列 CSV（2θ, 強度）。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        first = f.readline().strip()
    if not first.startswith("#"):
        return None
    meta = dict(kv.strip().split("=", 1) for kv in first[1:].split(";") if "=" in kv)
    try:
        dt = datetime.strptime(meta.get("date", ""), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = None
    return {
        "meas_id": "xrd-%s" % dt.strftime("%Y%m%d-%H%M%S") if dt else None,
        "instr": "xrd",
        "date": dt.strftime("%Y-%m-%d") if dt else "",
        "time": dt.strftime("%H:%M:%S") if dt else "",
        "sample": meta.get("sample", ""),
        "T_set_C": meta.get("T", ""),
        "format": "csv-2col",
    }


READERS = [
    # ({".csv"}, read_two_column_csv),     # 使うときはコメントを外す
]
