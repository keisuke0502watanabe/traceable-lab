"""雛形を書き出す。既にあるファイルは上書きしない（作ったもの・飛ばしたものを報告する）。"""
from __future__ import annotations

import json
import os
import re
from datetime import date

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
RESEARCH_DIRS = ["0-受け皿", "1-執筆/業績", "2-発表/1-conference", "3-文献", "4-データ",
                 "5-ラボ・教育", "6-事務・研究費", "9-アーカイブ"]


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9\-]+", "-", s.strip().lower())
    return re.sub(r"-{2,}", "-", s).strip("-") or "untitled"


def copy_tree(kind: str, dest: str, values: dict) -> tuple[list[str], list[str]]:
    src_root = os.path.join(TEMPLATES, kind)
    made, skipped = [], []
    for dp, dns, fns in os.walk(src_root):
        dns[:] = [d for d in dns if d != "__pycache__"]
        reldir = os.path.relpath(dp, src_root)
        outdir = os.path.normpath(os.path.join(dest, reldir))
        os.makedirs(outdir, exist_ok=True)
        for fn in sorted(fns):
            if fn.endswith(".pyc") or fn == ".DS_Store":
                continue
            out = os.path.join(outdir, fn)
            relout = os.path.relpath(out, dest)
            if os.path.exists(out):
                skipped.append(relout)
                continue
            with open(os.path.join(dp, fn), encoding="utf-8") as f:
                text = f.read()
            for k, v in values.items():
                text = text.replace("{{%s}}" % k, str(v))
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            made.append(relout)
    return made, skipped


def _write_new(path: str, text: str, made: list, skipped: list, base: str):
    rel = os.path.relpath(path, base)
    if os.path.exists(path):
        skipped.append(rel)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    made.append(rel)


def init_project(dest: str, name: str | None = None, sample: bool = False):
    dest = os.path.abspath(dest)
    name = name or os.path.basename(dest)
    today = date.today().isoformat()
    made, skipped = copy_tree("project", dest, {"name": name, "date": today})
    cfg = {
        "name": name,
        "created": today,
        "default_operator": "",
        "sample_aliases": [["^example ?fat[- ]?a$", "ExampleFat-A"]] if sample else [],
        "_help": "sample_aliases: [正規表現, 台帳に書く名前] の列。装置に入れた表記ゆれ（大文字小文字・略称）をそろえる",
    }
    _write_new(os.path.join(dest, "labkit.json"), json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", made, skipped, dest)
    fixes = "meas_id,column,value,reason\n"
    if sample:
        from .sample import FIXES_EXAMPLE
        fixes = FIXES_EXAMPLE
    _write_new(os.path.join(dest, "ledger_fixes.csv"), fixes, made, skipped, dest)
    _write_new(os.path.join(dest, "notes", today + ".md"),
               "# %s\n\n- **プロジェクトを作った**（`labkit init`）。最初に README.md の「二つの禁止」を読む\n" % today,
               made, skipped, dest)
    if sample:
        from .sample import write_all
        if os.path.isdir(os.path.join(dest, "DATA", "dsc")):
            skipped.append("DATA/dsc（練習用データ）")
        else:
            for p in write_all(os.path.join(dest, "DATA")):
                made.append(os.path.relpath(p, dest))
    return dest, made, skipped


def new_manuscript(root: str, slug: str, title: str | None = None):
    slug = _slug(slug)
    dest = os.path.join(root, "Documents", "manuscript-" + slug)
    made, skipped = copy_tree("manuscript", dest, {"title": title or slug, "slug": slug, "date": date.today().isoformat()})
    os.makedirs(os.path.join(dest, "figs", "out"), exist_ok=True)
    os.makedirs(os.path.join(dest, "materials"), exist_ok=True)
    return dest, made, skipped


def new_talk(root: str, slug: str, title: str | None = None):
    slug = _slug(slug)
    dest = os.path.join(root, "reports", "talk-" + slug)
    made, skipped = copy_tree("talk", dest, {"title": title or slug, "slug": slug, "date": date.today().isoformat()})
    for d in ("out", "old", os.path.join("src", "figs")):
        os.makedirs(os.path.join(dest, d), exist_ok=True)
    return dest, made, skipped


def research_map(dest: str):
    dest = os.path.abspath(dest)
    for d in RESEARCH_DIRS:
        os.makedirs(os.path.join(dest, d), exist_ok=True)
    made, skipped = copy_tree("research-map", dest, {"date": date.today().isoformat(), "path": dest})
    return dest, made, skipped


def new_audit(root: str, slug: str):
    """notes/audit-<slug>_<日付>.md を雛形から作る。"""
    today = date.today().isoformat()
    slug = _slug(slug)
    with open(os.path.join(TEMPLATES, "audit.md"), encoding="utf-8") as f:
        text = f.read().replace("{{slug}}", slug).replace("{{date}}", today)
    dest = os.path.join(root, "notes", "audit-%s_%s.md" % (slug, today))
    made, skipped = [], []
    _write_new(dest, text, made, skipped, root)
    return dest, made, skipped
