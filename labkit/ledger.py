"""labkit.ledger — 測定台帳（ledger.csv）の読み込み・絞り込み・パス解決。

台帳は ``labkit ledger`` が DATA を舐めて生成する一行一測定の CSV で、
``path`` 列はプロジェクト root（ledger.csv のある場所）起点の相対パス。
解析コードはファイルパスを手で書かず、必ずここを経由して raw を読む::

    from labkit import ledger
    L = ledger.load()                         # cwd から上へ ledger.csv を探す
    rows = L.select(instr="dsc", sample="PPP", Ta_C=(30, 50))
    for r in rows:
        print(r["meas_id"], L.resolve(r))     # 絶対パス

標準ライブラリのみ。
"""
from __future__ import annotations

import csv
import os
from typing import Callable, Iterable

LEDGER_NAME = "ledger.csv"
ENV_ROOT = "LABKIT_ROOT"

NUMERIC = ("Ta_C", "T_set_C", "mass_mg")


def find_root(start: str | None = None) -> str:
    """ledger.csv を持つディレクトリを探す。環境変数 → start から上へ の順。"""
    env = os.environ.get(ENV_ROOT)
    if env and os.path.exists(os.path.join(env, LEDGER_NAME)):
        return os.path.abspath(env)
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, LEDGER_NAME)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise FileNotFoundError(
                "%s が見つかりません（%s から上へ探索、環境変数 %s も未設定）"
                % (LEDGER_NAME, start or os.getcwd(), ENV_ROOT))
        d = parent


def _num(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _match(value: str, want) -> bool:
    """列の値と条件の照合。
    - str / int / float : 等しい（数値列は数値として比較）
    - list / tuple(len!=2) / set : いずれかに等しい
    - tuple(len==2)     : 数値列の閉区間 (lo, hi)、None で片側開放
    - callable          : want(value) が真
    """
    if callable(want):
        return bool(want(value))
    if isinstance(want, tuple) and len(want) == 2 and all(
            x is None or isinstance(x, (int, float)) for x in want):
        x = _num(value)
        if x is None:
            return False
        lo, hi = want
        return (lo is None or x >= lo) and (hi is None or x <= hi)
    if isinstance(want, (list, tuple, set, frozenset)):
        return any(_match(value, w) for w in want)
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        x = _num(value)
        return x is not None and x == float(want)
    return value == str(want)


class Ledger:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.path = os.path.join(self.root, LEDGER_NAME)
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.columns = list(reader.fieldnames or [])
            self.rows = list(reader)
        self._by_id = {r["meas_id"]: r for r in self.rows}

    # -- 参照 ---------------------------------------------------------------
    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def get(self, meas_id: str) -> dict:
        try:
            return self._by_id[meas_id]
        except KeyError:
            raise KeyError("台帳に無い meas_id: %s" % meas_id) from None

    def has(self, meas_id: str) -> bool:
        return meas_id in self._by_id

    def resolve(self, row_or_id) -> str:
        """行（または meas_id）から raw の絶対パス。"""
        row = self.get(row_or_id) if isinstance(row_or_id, str) else row_or_id
        return os.path.join(self.root, *row["path"].split("/"))

    def derived(self, row_or_id) -> list[str]:
        """derived 列（積分済みの 1D データなど）を絶対パスのリストに。"""
        row = self.get(row_or_id) if isinstance(row_or_id, str) else row_or_id
        out = []
        for item in (row.get("derived") or "").split(";"):
            item = item.strip()
            if not item:
                continue
            p = item.split("(")[0]
            out.append(os.path.join(self.root, *p.split("/")))
        return out

    # -- 絞り込み -----------------------------------------------------------
    def select(self, where: Callable[[dict], bool] | None = None, **conds) -> list[dict]:
        """列名=条件 で絞る。条件の書き方は _match を参照。
        例: select(instr="dsc", sample=["PPP", "C8TAG"], Ta_C=(30, 50), status=lambda s: s != "bad")
        """
        out = []
        for r in self.rows:
            if where is not None and not where(r):
                continue
            ok = True
            for col, want in conds.items():
                if col not in r:
                    raise KeyError("台帳に無い列: %s（列: %s）" % (col, ", ".join(self.columns)))
                if not _match(r[col], want):
                    ok = False
                    break
            if ok:
                out.append(r)
        return out

    def ids(self, rows: Iterable[dict]) -> list[str]:
        return [r["meas_id"] for r in rows]

    def series(self, rows: Iterable[dict] | None = None) -> dict[str, list[dict]]:
        """(instr, session, series) ごとにまとめる。温度系列を一塊で扱いたいとき。"""
        groups: dict[str, list[dict]] = {}
        for r in (rows if rows is not None else self.rows):
            key = "%s/%s/%s" % (r["instr"], r.get("session", ""), r.get("series", ""))
            groups.setdefault(key, []).append(r)
        return groups

    # -- 熱履歴 -------------------------------------------------------------
    @staticmethod
    def steps(row: dict) -> list[str]:
        """thermal_history を段ごとのリストに（'25→100@15', 'hold100/15min', ...）。"""
        return [s.strip() for s in (row.get("thermal_history") or "").split(">") if s.strip()]

    @staticmethod
    def holds(row: dict) -> list[tuple[float, float]]:
        """DSC 記法の hold 段を (温度, 分) の列で返す。"""
        out = []
        for s in Ledger.steps(row):
            if s.startswith("hold") and "/" in s:
                t, m = s[4:].split("/", 1)
                try:
                    out.append((float(t), float(m.replace("min", ""))))
                except ValueError:
                    pass
        return out


def load(root: str | None = None) -> Ledger:
    """root を省略すると cwd から上へ ledger.csv を探す。"""
    return Ledger(root or find_root())


if __name__ == "__main__":     # 動作確認: python3 -m labkit.ledger [root]
    import sys
    L = load(sys.argv[1] if len(sys.argv) > 1 else None)
    print("root:", L.root, "| rows:", len(L))
    from collections import Counter
    for (i, s), n in sorted(Counter((r["instr"], r["sample"]) for r in L).items()):
        print("  %-22s %-8s %5d" % (i, s, n))
