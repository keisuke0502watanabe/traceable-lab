"""測定ファイルの読み取り器（reader）。

reader は「ファイル 1 本 → 台帳の 1 行（dict）」を返す関数。読めないファイルには None を返す。
返す dict に入れられるキー（どれも省略可。足りない分は台帳側で空欄になる）::

    meas_id          測定 ID。ファイルの中身（測定日時・走査番号）から決める。省略すると内容のハッシュ
    instr            装置の種類（dsc, xrd, saxs, ...）
    date, time       測定日時（YYYY-MM-DD / HH:MM:SS）
    sample           試料名
    mass_mg          質量
    operator         実験者
    thermal_history  熱履歴の短い記法  例: 25→80@15 > hold80/15min > 80→-20@10
    Ta_C, T_set_C    保持温度・設定温度
    format           ファイル形式の名前
    session, series  まとめて扱う単位
    _dup_key         同じ測定のコピーを見分けるキー（省略すると meas_id）

自分の装置の形式を足すときは、プロジェクトの ``tools/readers.py`` に関数を書いて
``READERS`` に登録する（雛形がそこにある）。
"""
from __future__ import annotations

from .pyris_txt import read as read_pyris_txt
from .rigaku_ras import read as read_rigaku_ras
from .common import thermal_history_ta

# (拡張子の集合, reader) の列。上から順に試し、最初に None 以外を返したものを使う
BUILTIN = [
    ({".txt"}, read_pyris_txt),
    ({".ras"}, read_rigaku_ras),
]

__all__ = ["BUILTIN", "read_pyris_txt", "read_rigaku_ras", "thermal_history_ta"]
