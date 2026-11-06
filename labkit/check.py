"""根拠の鎖の点検（labkit check）と、影響を受ける解析の洗い出し（labkit downstream）。

check は読むだけ。DATA・台帳・解析は何も変えない。見るのは「仕組みで機械的に分かること」:

  生データ   入力ファイルが消えた / 書き換わった（DATA は凍結のはず）/ 0 バイトのファイル / 台帳に入らないファイル
  台帳       解析を作ったあとで入力の行の値が変わった（質量の修正、status: bad など）/ 台帳から消えた
  解析       used なのに置き換え済み / 上流（based_on）が rejected・置き換え済み・誤りあり /
             スクリプトが作成時から変わった / 検証で誤り（error）が記録されている / 図が無い / notes が空
  検証       used のうち、一度も検証の記録（labkit verify）が無いもの

数値そのものの正しさ（並び順の取り違え、補間で埋めた値、決め打ちの定数 …）は機械では分からない。
それは点検メモ（labkit audit）と、生データから別のコードで出し直す検算で確かめ、結果を labkit verify で残す。
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import date

from . import analysis as _an
from .build_ledger import collect, load_project_readers, walk
from .readers import BUILTIN

LEVELS = ("error", "warn", "info")
LEVEL_JA = {"error": "誤り", "warn": "要注意", "info": "参考"}


def _ledger(root: str) -> dict:
    p = os.path.join(root, "ledger.csv")
    if not os.path.exists(p):
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["meas_id"]: r for r in csv.DictReader(f)}


def _graph(items):
    """ana_id → 下流（based_on でこれを使う解析）の集合、と superseded_by。"""
    down = defaultdict(set)
    sup_by = {}
    for A in items:
        for up in _an.as_list(A.manifest.get("based_on")):
            down[up].add(A.ana_id)
        s = A.manifest.get("supersedes")
        if s:
            sup_by[s] = A.ana_id
    return down, sup_by


def _last_check(m: dict):
    c = m.get("checks") or []
    return c[-1] if c else None


def run(root: str) -> list[dict]:
    root = os.path.abspath(root)
    L = _ledger(root)
    items = _an.list_all(root)
    by_id = {A.ana_id: A for A in items}
    down, sup_by = _graph(items)
    F: list[dict] = []

    def add(level, kind, target, msg):
        F.append({"level": level, "kind": kind, "target": target, "message": msg})

    # -- 生データ ---------------------------------------------------------------
    data = os.path.join(root, "DATA")
    if os.path.isdir(data):
        for p in walk(data):
            if os.path.getsize(p) == 0:
                add("error", "zero_byte", os.path.relpath(p, root),
                    "0 バイトのファイル。書き出しか変換が途中で止まった可能性。台帳には入っていない")
        readers = load_project_readers(root) + BUILTIN
        rows, skipped = collect(root, readers)
        known = {r["meas_id"] for r in rows}
        for mid in sorted(set(L) - known - {m for m in L if "-" in m and m.rsplit("-", 1)[0] in known}):
            add("warn", "ledger_stale", mid, "台帳にあるが、いまの DATA からは作られない行。labkit ledger で作り直す")
        for ext, n in skipped.most_common():
            add("info", "unread_files", ext, "%d 本のファイルを台帳に入れていない（reader が無い形式）" % n)

    # -- 解析 -----------------------------------------------------------------
    for A in items:
        m, aid = A.manifest, A.ana_id
        status = m.get("status")
        used = status == "used"
        # 入力
        for i in m.get("inputs", []):
            row = L.get(i)
            if row is None:
                add("error", "input_missing", aid, "入力 %s が台帳に無い" % i)
                continue
            path = os.path.join(root, *row["path"].split("/"))
            sha = (m.get("inputs_sha1") or {}).get(i)
            if not os.path.isfile(path):
                add("error", "data_missing", aid, "入力 %s のファイルが無い: %s" % (i, row["path"]))
            elif sha and _an.file_sha1(path) != sha:
                add("error", "data_changed", aid, "入力 %s のファイルが解析のあとで書き換わった: %s" % (i, row["path"]))
            snap = (m.get("inputs_rows") or {}).get(i)
            if snap:
                for k, v in snap.items():
                    if row.get(k, "") != v:
                        lvl = "warn" if used else "info"
                        add(lvl, "ledger_changed", aid, "入力 %s の台帳の %s が変わった: %r → %r" % (i, k, v, row.get(k, "")))
            if used and row.get("status") == "bad" and not (snap and snap.get("status") != "bad"):
                add("warn", "input_bad", aid, "入力 %s は台帳で status: bad" % i)
        # 系譜
        if used and aid in sup_by:
            add("warn", "superseded_used", aid, "used のまま %s に置き換えられている。古い版を引用していないか" % sup_by[aid])
        for up in _an.as_list(m.get("based_on")):
            U = by_id.get(up)
            if U is None:
                add("error", "upstream_missing", aid, "上流 %s が無い" % up)
                continue
            um = U.manifest
            lc = _last_check(um)
            if um.get("status") == "rejected":
                add("warn", "upstream_rejected", aid, "上流 %s が rejected" % up)
            if up in sup_by:
                add("warn", "upstream_superseded", aid, "上流 %s は %s に置き換え済み。作り直しが要るかもしれない" % (up, sup_by[up]))
            if lc and lc.get("result") == "error":
                add("warn", "upstream_error", aid, "上流 %s の検証で誤りが記録されている（%s）" % (up, lc.get("note", "")))
        # コード
        for path, sha in (m.get("code") or {}).items():
            ap = os.path.join(root, path)
            if not os.path.isfile(ap):
                add("info", "code_missing", aid, "スクリプト %s が無い（動かした・消した）" % path)
            elif _an.file_sha1(ap) != sha:
                add("warn" if used else "info", "code_changed", aid,
                    "スクリプト %s が解析のあとで変わった。同じ結果になるか作り直して確かめる" % path)
        # 検証
        lc = _last_check(m)
        if lc and lc.get("result") == "error":
            add("error", "check_error", aid, "検証で誤り: %s%s" % (lc.get("note", ""), "（%s）" % lc["report"] if lc.get("report") else ""))
            for d in sorted(down.get(aid, ())):
                add("warn", "downstream_of_error", d, "上流 %s に誤りがある" % aid)
        elif lc and lc.get("result") == "caution" and used:
            add("info", "check_caution", aid, "検証で要注意: %s" % lc.get("note", ""))
        if used and not lc:
            add("info", "unverified", aid, "used だが検証の記録が無い（labkit verify）")
        # 中身
        outs = m.get("outputs") or []
        if used and not outs and not m.get("external_dir"):
            add("warn", "no_outputs", aid, "used なのに out/ が空")
        if used and os.path.exists(A.notes_path):
            with open(A.notes_path, encoding="utf-8") as f:
                if "（結果が出たら数行で）" in f.read():
                    add("info", "notes_unfilled", aid, "notes.md の「分かったこと」が空")
    order = {k: i for i, k in enumerate(LEVELS)}
    F.sort(key=lambda x: (order[x["level"]], x["kind"], x["target"]))
    return F


def downstream(root: str, target: str) -> list[str]:
    """target（ana_id か、スクリプトのパス）の影響を受ける解析を、作り直す順（上流が先）に返す。

    - ana_id: based_on でそれを使う解析を下流へたどる
    - パス: code にそのパスを持つ解析と、その下流
    置き換え済み（superseded_by あり）の版は除く。作り直すのは最新の版だけでよいため。
    """
    root = os.path.abspath(root)
    items = _an.list_all(root)
    down, sup_by = _graph(items)
    if target.startswith("ana-"):
        start = {target}
    else:
        key = os.path.relpath(os.path.abspath(target), root).replace(os.sep, "/") if os.path.exists(target) else target
        start = {A.ana_id for A in items if key in (A.manifest.get("code") or {})
                 or A.manifest.get("procedure") == key}
    seen, order = set(), []

    def visit(a):
        if a in seen:
            return
        seen.add(a)
        order.append(a)
        for d in sorted(down.get(a, ())):
            visit(d)

    for s in sorted(start):
        visit(s)
    # 上流が先になるよう、based_on の深さで並べ直す
    depth = {}
    by_id = {A.ana_id: A for A in items}

    def dep(a, stack=()):
        if a in depth:
            return depth[a]
        ups = [u for u in _an.as_list(by_id[a].manifest.get("based_on")) if u in by_id and u not in stack] if a in by_id else []
        depth[a] = 1 + max((dep(u, stack + (a,)) for u in ups), default=0)
        return depth[a]

    return [a for a in sorted(order, key=lambda a: (dep(a), a)) if a not in sup_by]


def write_report(root: str, findings: list[dict]) -> str:
    p = os.path.join(root, "reports", "check_report.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    n = defaultdict(int)
    for f in findings:
        n[f["level"]] += 1
    lines = ["# 根拠の鎖の点検（labkit check, %s）" % date.today().isoformat(), "",
             "誤り %d ・ 要注意 %d ・ 参考 %d。読むだけの点検で、何も変えていない。" % (n["error"], n["warn"], n["info"]), ""]
    for lvl in LEVELS:
        sub = [f for f in findings if f["level"] == lvl]
        if not sub:
            continue
        lines += ["## %s（%d）" % (LEVEL_JA[lvl], len(sub)), "", "| 種類 | 対象 | 内容 |", "|---|---|---|"]
        lines += ["| %s | `%s` | %s |" % (f["kind"], f["target"], f["message"].replace("|", "\\|")) for f in sub]
        lines.append("")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return p


def summary(findings: list[dict], limit: int = 30) -> str:
    out = []
    for lvl in LEVELS:
        sub = [f for f in findings if f["level"] == lvl]
        if not sub:
            continue
        out.append("%s %d 件" % (LEVEL_JA[lvl], len(sub)))
        for f in sub[:limit]:
            out.append("  [%s] %s: %s" % (f["kind"], f["target"], f["message"]))
        if len(sub) > limit:
            out.append("  … ほか %d 件（reports/check_report.md）" % (len(sub) - limit))
    return "\n".join(out) or "問題は見つからなかった"
