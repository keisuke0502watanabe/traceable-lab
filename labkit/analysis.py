"""labkit.analysis — 解析の単位「analysis」を analyses/ に作り、系譜を manifest に残す。

一つの問いに、台帳のこれらの行（meas_id）へ、この手続きをこのパラメータで当てた一回 = 一 analysis。
フォルダ名 = ana_id = ``ana-YYYYMMDD-<slug>``。中身は::

    analyses/ana-20260914-ppp-avrami-ta45/
        manifest.json   機械可読: inputs(meas_id) / tool / procedure / params / results / status / supersedes
        notes.md        人間向け: 問い・分かったこと・次
        out/            図・表・pdf。形式は問わない

使い方::

    from labkit import ledger, analysis
    L = ledger.load()
    rows = L.select(instr="dsc", sample="PPP", Ta_C=45)
    A = analysis.new(L, "ppp-avrami-ta45",
                     question="PPP Ta=45 の等温結晶化を Avrami で記述できるか",
                     inputs=rows, procedure="labkit.kinetics.avrami",
                     params={"t0Mode": "induction", "baseline": "exp"})
    ...  # 計算。図は A.out("xt_curve.png") に保存
    A.finish(results={"n": 2.8, "n_ci95": [2.6, 3.1]}, status="used")

禁止: analyses/ のフォルダを消さない。やり直しは supersedes=前の ana_id で新しく作る。
標準ライブラリのみ。
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from datetime import datetime

from . import __version__ as LABKIT_VERSION
from .ledger import Ledger

ANALYSES_DIR = "analyses"
INDEX_NAME = "analyses_index.csv"
STATUSES = ("tried", "used", "rejected")

INDEX_COLUMNS = ["ana_id", "created", "status", "question", "procedure",
                 "n_inputs", "instr", "samples", "supersedes", "superseded_by", "based_on", "dir"]

NOTES_TEMPLATE = """# {ana_id}

## 問い
{question}

## 分かったこと
（結果が出たら数行で）

## 次
（この analysis の続きに何をするか、あるいは捨てた理由）
"""


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9\-]+", "-", s.strip().lower())
    return re.sub(r"-{2,}", "-", s).strip("-") or "analysis"


def _git_commit() -> str:
    """labkit 自身のリポジトリのコミット（取れなければ空）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        out = subprocess.run(["git", "-C", here, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


class Analysis:
    def __init__(self, root: str, ana_id: str):
        self.root = os.path.abspath(root)
        self.ana_id = ana_id
        self.dir = os.path.join(self.root, ANALYSES_DIR, ana_id)
        self.manifest_path = os.path.join(self.dir, "manifest.json")
        self.notes_path = os.path.join(self.dir, "notes.md")
        self.out_dir = os.path.join(self.dir, "out")
        self.manifest: dict = {}
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, encoding="utf-8") as f:
                self.manifest = json.load(f)

    # -- 出力 ---------------------------------------------------------------
    def out(self, name: str) -> str:
        """out/ の中のパスを返す（ディレクトリは作る）。図はここに保存する。"""
        os.makedirs(self.out_dir, exist_ok=True)
        return os.path.join(self.out_dir, name)

    def save_json(self, name: str, obj) -> str:
        p = self.out(name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return p

    # -- manifest -----------------------------------------------------------
    def write_manifest(self):
        os.makedirs(self.dir, exist_ok=True)
        self.manifest["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        return self.manifest_path

    def finish(self, results: dict | None = None, status: str = "used", note: str = ""):
        """結果の要約値と status を書き込む。status は tried / used / rejected。"""
        if status not in STATUSES:
            raise ValueError("status は %s のどれか" % "/".join(STATUSES))
        if results is not None:
            self.manifest["results"] = results
        self.manifest["status"] = status
        if note:
            self.manifest["note"] = note
        # out/ の一覧も残す（後で index から図を探せるように）
        if os.path.isdir(self.out_dir):
            self.manifest["outputs"] = sorted(os.listdir(self.out_dir))
        return self.write_manifest()

    def __repr__(self):
        return "Analysis(%s, status=%s)" % (self.ana_id, self.manifest.get("status"))


def new(ledger: Ledger, slug: str, question: str, inputs, procedure: str,
        params: dict | None = None, supersedes: str | None = None,
        date: datetime | None = None, extra: dict | None = None) -> Analysis:
    """analyses/ に新しい analysis を作る。inputs は台帳の行か meas_id の列。"""
    ids = [r["meas_id"] if isinstance(r, dict) else str(r) for r in inputs]
    unknown = [i for i in ids if not ledger.has(i)]
    if unknown:
        raise KeyError("台帳に無い meas_id: %s" % ", ".join(unknown[:5]))
    if supersedes:
        prev = os.path.join(ledger.root, ANALYSES_DIR, supersedes)
        if not os.path.isdir(prev):
            raise FileNotFoundError("supersedes に指定した analysis が無い: %s" % supersedes)

    d = (date or datetime.now()).strftime("%Y%m%d")
    base = "ana-%s-%s" % (d, _slug(slug))
    ana_id, k = base, 1
    while os.path.exists(os.path.join(ledger.root, ANALYSES_DIR, ana_id)):
        k += 1
        ana_id = "%s-%d" % (base, k)

    rows = [ledger.get(i) for i in ids]
    A = Analysis(ledger.root, ana_id)
    A.manifest = {
        "ana_id": ana_id,
        "question": question,
        "inputs": ids,
        "inputs_summary": {
            "instr": sorted({r["instr"] for r in rows}),
            "samples": sorted({r["sample"] for r in rows}),
            "n": len(ids),
        },
        "ledger": {"path": os.path.relpath(ledger.path, ledger.root),
                   "mtime": datetime.fromtimestamp(os.path.getmtime(ledger.path)).isoformat(timespec="seconds")},
        "tool": {"name": "labkit", "version": LABKIT_VERSION, "commit": _git_commit()},
        "procedure": procedure,
        "params": params or {},
        "results": None,
        "status": "tried",
        "supersedes": supersedes,
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if extra:
        A.manifest.update(extra)
    os.makedirs(A.out_dir, exist_ok=True)
    A.write_manifest()
    with open(A.notes_path, "w", encoding="utf-8") as f:
        f.write(NOTES_TEMPLATE.format(ana_id=ana_id, question=question))
    return A


def register(ledger: Ledger, slug: str, question: str, inputs, procedure: str,
             external_dir: str, date: datetime, status: str = "used",
             params: dict | None = None, outputs: list[str] | None = None,
             based_on: str | None = None, note: str = "") -> Analysis:
    """DATA の中などにすでにある解析（動かせない・動かさない）に、系譜だけ後付けする。

    analyses/<ana_id>/ には manifest.json と notes.md だけを置き、図や scripts の実体は
    external_dir（root 起点の相対パス）に残す。trace / index はこの欄を見て辿る。
    outputs を省略すると external_dir 以下の図ファイル（png/pdf/svg/html/csv）を拾う。
    """
    ids = [r["meas_id"] if isinstance(r, dict) else str(r) for r in inputs]
    unknown = [i for i in ids if not ledger.has(i)]
    if unknown:
        raise KeyError("台帳に無い meas_id: %s" % ", ".join(unknown[:5]))
    if status not in STATUSES:
        raise ValueError("status は %s のどれか" % "/".join(STATUSES))
    ext_abs = os.path.join(ledger.root, *external_dir.split("/"))
    if not os.path.isdir(ext_abs):
        raise FileNotFoundError("external_dir が無い: %s" % ext_abs)

    base = "ana-%s-%s" % (date.strftime("%Y%m%d"), _slug(slug))
    ana_id, k = base, 1
    while os.path.exists(os.path.join(ledger.root, ANALYSES_DIR, ana_id)):
        k += 1
        ana_id = "%s-%d" % (base, k)

    if outputs is None:
        outputs = []
        for dp, dns, fns in os.walk(ext_abs):
            dns[:] = [d for d in dns if not d.startswith((".", "__"))]
            for fn in sorted(fns):
                if fn.lower().endswith((".png", ".pdf", ".svg", ".html", ".csv")):
                    outputs.append(os.path.relpath(os.path.join(dp, fn), ext_abs).replace(os.sep, "/"))

    rows = [ledger.get(i) for i in ids]
    A = Analysis(ledger.root, ana_id)
    A.manifest = {
        "ana_id": ana_id,
        "question": question,
        "inputs": ids,
        "inputs_summary": {
            "instr": sorted({r["instr"] for r in rows}),
            "samples": sorted({r["sample"] for r in rows}),
            "n": len(ids),
        },
        "ledger": {"path": os.path.relpath(ledger.path, ledger.root),
                   "mtime": datetime.fromtimestamp(os.path.getmtime(ledger.path)).isoformat(timespec="seconds")},
        "tool": {"name": "external", "version": "", "commit": ""},
        "procedure": procedure,
        "params": params or {},
        "results": None,
        "status": status,
        "supersedes": None,
        "based_on": based_on,
        "external_dir": external_dir,
        "outputs": outputs,
        "registered": True,
        "note": note,
        "created": date.astimezone().isoformat(timespec="seconds") if date.tzinfo else date.isoformat(timespec="seconds"),
    }
    os.makedirs(A.dir, exist_ok=True)
    A.write_manifest()
    with open(A.notes_path, "w", encoding="utf-8") as f:
        f.write(NOTES_TEMPLATE.format(ana_id=ana_id, question=question)
                + "\n## 実体の場所\n`%s`（後付け登録。図と scripts はそこにある）\n" % external_dir)
    return A


def open_(root: str, ana_id: str) -> Analysis:
    A = Analysis(root, ana_id)
    if not A.manifest:
        raise FileNotFoundError("analysis が無い: %s" % A.dir)
    return A


def list_all(root: str) -> list[Analysis]:
    base = os.path.join(root, ANALYSES_DIR)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        if name.startswith("ana-") and os.path.exists(os.path.join(base, name, "manifest.json")):
            out.append(Analysis(root, name))
    return out


def build_index(root: str) -> str:
    """全 manifest を舐めて analyses_index.csv を作る（生成物。手で編集しない）。"""
    items = list_all(root)
    superseded_by: dict[str, str] = {}
    for A in items:
        s = A.manifest.get("supersedes")
        if s:
            superseded_by[s] = A.ana_id
    p = os.path.join(root, INDEX_NAME)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        w.writeheader()
        for A in items:
            m = A.manifest
            s = m.get("inputs_summary", {})
            w.writerow({
                "ana_id": A.ana_id,
                "created": (m.get("created") or "")[:10],
                "status": m.get("status", ""),
                "question": m.get("question", ""),
                "procedure": m.get("procedure", ""),
                "n_inputs": s.get("n", len(m.get("inputs", []))),
                "instr": ";".join(s.get("instr", [])),
                "samples": ";".join(s.get("samples", [])),
                "supersedes": m.get("supersedes") or "",
                "superseded_by": superseded_by.get(A.ana_id, ""),
                "based_on": m.get("based_on") or "",
                "dir": m.get("external_dir") or os.path.relpath(A.dir, root),
            })
    return p


def trace(root: str, ana_id: str) -> dict:
    """根拠を辿る: ana_id → inputs(meas_id) → path。レポートの脚注から raw まで。"""
    A = open_(root, ana_id)
    L = Ledger(root)
    return {
        "ana_id": ana_id,
        "status": A.manifest.get("status"),
        "supersedes": A.manifest.get("supersedes"),
        "based_on": A.manifest.get("based_on"),
        "dir": A.manifest.get("external_dir") or os.path.relpath(A.dir, root),
        "inputs": [{"meas_id": i,
                    "path": L.get(i)["path"] if L.has(i) else None,
                    "thermal_history": L.get(i)["thermal_history"] if L.has(i) else None}
                   for i in A.manifest.get("inputs", [])],
        "outputs": A.manifest.get("outputs", []),
    }


if __name__ == "__main__":     # python3 -m labkit.analysis index [root] / trace <ana_id> [root]
    import sys
    from .ledger import find_root
    cmd = sys.argv[1] if len(sys.argv) > 1 else "index"
    if cmd == "index":
        root = sys.argv[2] if len(sys.argv) > 2 else find_root()
        print(build_index(root))
    elif cmd == "trace":
        root = sys.argv[3] if len(sys.argv) > 3 else find_root()
        print(json.dumps(trace(root, sys.argv[2]), ensure_ascii=False, indent=2))
    else:
        sys.exit("usage: python3 -m labkit.analysis index [root] | trace <ana_id> [root]")
