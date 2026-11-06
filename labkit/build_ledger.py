"""DATA/ を読んで測定台帳 ledger.csv を作り直す（標準ライブラリのみ）。

台帳の考え方
  一行 = 一測定。DATA/ のファイルは動かさない。分類や判断は台帳の列に書く。
  meas_id はファイルの中身（測定日時・走査番号）から決めるので、ファイルが増えても変わらない。

再生成しても残るもの
  - 手で書く列 status / tags / note（meas_id で突き合わせる）
  - operator / ref は、手で書いた値があればそちらを残す
  - sample / thermal_history / mass_mg / Ta_C は、機械で埋まらなかったときだけ前の値を残す
    （XRD の温度系列の熱履歴などを手で書いておける）
  - ledger_fixes.csv（meas_id, column, value, reason）の値は最後に必ず上書きする。
    装置への入力ミス（質量の打ち間違いなど）を、DATA を触らずに根拠つきで直すための表

同じ測定のコピー
  バックアップや zip の展開でできたコピーは行を持たず、正とした行の duplicates 列に並べる。
  正にするのはパスに previous / backup / copy / old を含まない、短いほう。

使い方
  labkit ledger                 # プロジェクトの中で
  labkit ledger --root PATH
出力
  ledger.csv       全行
  ledger_gaps.csv  日付・試料・熱履歴のどれかが埋まらなかった行（手で埋める宿題）
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict

from .readers import BUILTIN

COLUMNS = [
    "meas_id", "instr", "date", "time", "sample", "mass_mg", "operator",
    "thermal_history", "Ta_C", "T_set_C",
    "path", "format", "session", "series", "duplicates",
    "status", "tags", "note", "gaps", "ref",
]
MANUAL = ["status", "tags", "note"]                       # 常に手書きの値
MANUAL_OR_DEFAULT = ["operator", "ref"]                   # 手書きがあれば優先
FILL_IF_EMPTY = ["sample", "thermal_history", "mass_mg", "Ta_C", "date", "time"]   # 機械が空なら前の値
GAP_COLUMNS = ["date", "sample", "thermal_history"]
CONFIG_NAME = "labkit.json"
FIXES_NAME = "ledger_fixes.csv"
DUP_WORDS = ("previous", "backup", "copy", "old", "_tmp", "コピー")


def find_project_root(start: str | None = None) -> str:
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, CONFIG_NAME)) or os.path.exists(os.path.join(d, "ledger.csv")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise FileNotFoundError("labkit のプロジェクトが見つかりません（%s が無い）。labkit init で作れます。" % CONFIG_NAME)
        d = parent


def load_config(root: str) -> dict:
    p = os.path.join(root, CONFIG_NAME)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_project_readers(root: str):
    """プロジェクトの tools/readers.py の READERS を読む（無ければ空）。"""
    p = os.path.join(root, "tools", "readers.py")
    if not os.path.exists(p):
        return []
    spec = importlib.util.spec_from_file_location("project_readers", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "READERS", []))


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(root: str, p: str) -> str:
    return os.path.relpath(p, root).replace(os.sep, "/")


def dup_rank(relpath: str):
    r = relpath.lower()
    score = sum(100 for w in DUP_WORDS if w in r)
    return (score, len(r), r)


def norm_sample(text: str, aliases) -> str:
    t = (text or "").strip()
    for pat, name in aliases:
        if re.search(pat, t, re.I):
            return name
    return t


def walk(data: str):
    for dp, dns, fns in os.walk(data):
        dns[:] = sorted(d for d in dns if not d.startswith((".", "__")))
        for fn in sorted(fns):
            if not fn.startswith(".") and fn.lower() not in ("readme.md", "readme.txt"):
                yield os.path.join(dp, fn)


def load_previous(path: str) -> dict:
    keep = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                keep[r["meas_id"]] = r
    return keep


def load_fixes(root: str) -> list[dict]:
    p = os.path.join(root, FIXES_NAME)
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("meas_id") and r.get("column")]


def collect(root: str, readers) -> tuple[list[dict], Counter]:
    data = os.path.join(root, "DATA")
    groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    skipped: Counter = Counter()
    for p in walk(data):
        ext = os.path.splitext(p)[1].lower()
        if os.path.getsize(p) == 0:            # 書き出し・変換が途中で落ちたファイル。黙って抜けないように数える
            skipped["(0 バイト)"] += 1
            print("  0 バイトのファイル: %s" % rel(root, p), file=sys.stderr)
            continue
        row = None
        for exts, fn in readers:
            if ext in exts:
                try:
                    row = fn(p)
                except Exception as e:      # 一本の壊れたファイルで全体を止めない
                    print("  読めない: %s (%s)" % (rel(root, p), e), file=sys.stderr)
                    row = None
                if row:
                    break
        if not row:
            skipped[ext or "(拡張子なし)"] += 1
            continue
        key = row.pop("_dup_key", None) or "md5|" + md5(p)
        groups[key].append((p, row))

    rows = []
    for key, items in groups.items():
        items.sort(key=lambda it: dup_rank(rel(root, it[0])))
        p, row = items[0]
        relp = rel(root, p)
        if not row.get("meas_id"):
            row["meas_id"] = "%s-unknown-%s" % (row.get("instr") or "file", md5(p)[:8])
        row["path"] = relp
        row["duplicates"] = ";".join(rel(root, q) for q, _ in items[1:])
        row.setdefault("session", os.path.dirname(relp).split("/", 1)[-1] if "/" in relp else "")
        rows.append(row)
    return rows, skipped


def build(root: str | None = None, quiet: bool = False) -> str:
    root = os.path.abspath(root or find_project_root())
    if not os.path.isdir(os.path.join(root, "DATA")):
        raise FileNotFoundError("DATA/ がありません: %s" % root)
    cfg = load_config(root)
    aliases = cfg.get("sample_aliases", [])
    readers = load_project_readers(root) + BUILTIN
    out = os.path.join(root, "ledger.csv")
    prev = load_previous(out)

    rows, skipped = collect(root, readers)

    # meas_id の衝突（別の測定が同じ時刻）は枝番
    seen: Counter = Counter()
    for r in sorted(rows, key=lambda r: r["path"]):
        seen[r["meas_id"]] += 1
        if seen[r["meas_id"]] > 1:
            r["meas_id"] += "-%d" % seen[r["meas_id"]]

    extra_cols: set[str] = set()
    for r in rows:
        r["sample"] = norm_sample(r.get("sample", ""), aliases)
        if not r.get("operator") and cfg.get("default_operator"):
            r["operator"] = cfg["default_operator"]
        old = prev.get(r["meas_id"], {})
        for k in MANUAL:
            r[k] = old.get(k, "")
        for k in MANUAL_OR_DEFAULT:
            r[k] = old.get(k, "") or r.get(k, "")
        for k in FILL_IF_EMPTY:
            if not r.get(k) and old.get(k):
                r[k] = old[k]
        extra_cols |= {k for k in r if k not in COLUMNS}

    by_id = {r["meas_id"]: r for r in rows}
    for fx in load_fixes(root):
        r = by_id.get(fx["meas_id"])
        if r is not None:
            r[fx["column"]] = fx.get("value", "")

    for r in rows:
        r["gaps"] = ";".join(k for k in GAP_COLUMNS if not r.get(k))
    columns = COLUMNS + sorted(extra_cols)
    for r in rows:
        for k in columns:
            r.setdefault(k, "")
    rows.sort(key=lambda r: (r["instr"], r["date"] or "9999", r["time"], r["meas_id"]))

    for name, subset in ((out, rows), (os.path.join(root, "ledger_gaps.csv"), [r for r in rows if r["gaps"]])):
        with open(name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(subset)

    if not quiet:
        by_instr = Counter(r["instr"] for r in rows)
        print("台帳: %d 行 -> %s" % (len(rows), out))
        for k, n in sorted(by_instr.items()):
            print("  %-10s %5d" % (k, n))
        print("  空欄のある行 %d（ledger_gaps.csv）、コピーを持つ行 %d、引き継いだ手書きの行 %d"
              % (sum(1 for r in rows if r["gaps"]), sum(1 for r in rows if r["duplicates"]),
                 sum(1 for r in rows if any(r.get(k) for k in MANUAL))))
        if skipped:
            print("  読まなかったファイル: " + ", ".join("%s %d" % kv for kv in skipped.most_common()))
            print("  （自分の形式は tools/readers.py に reader を書くと台帳に入る）")
    return out
