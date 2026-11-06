"""labkit のコマンド。

    labkit map ~/Research                 研究フォルダ全体の地図（0-受け皿 … 9-アーカイブ、README、MOVES）
    labkit init my-project [--sample]     実験プロジェクトの雛形（--sample で練習用の合成 DSC つき）
    labkit demo my-demo                   雛形 + 練習データ + 見本の解析 2 本 + ギャラリーまで一気に

    （以下はプロジェクトの中で。--root で場所を指定してもよい）
    labkit ledger                         DATA/ から台帳を作り直す
    labkit new <slug> -q "問い" [--where instr=dsc sample=X]   解析フォルダを作る
    labkit index                          analyses_index.csv を作り直す
    labkit gallery                        図ギャラリーと解析ビューアを作り直す
    labkit refresh                        ledger → index → gallery をまとめて
    labkit trace <ana_id>                 図の根拠を生データまで辿る
    labkit manuscript <名前> [--title]    論文の作業フォルダ Documents/manuscript-<名前>/
    labkit talk <名前> [--title]          発表の作業フォルダ reports/talk-<名前>/
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import __version__, analysis, build_ledger, gallery, ledger, scaffold


def _report(dest, made, skipped):
    print("%s: %d 個作った" % (dest, len(made)))
    if skipped:
        print("  既にあったので触らなかった: %d 個（%s%s）" % (len(skipped), ", ".join(skipped[:5]), " …" if len(skipped) > 5 else ""))


def _root(a) -> str:
    return os.path.abspath(a.root) if a.root else build_ledger.find_project_root()


def _refresh(root: str):
    if os.path.isdir(os.path.join(root, "DATA")):
        build_ledger.build(root)
    print("解析一覧: -> %s" % analysis.build_index(root))
    gallery.build(root)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="labkit", description="図から生データまで辿れる研究フォルダを作り、回す。",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--version", action="version", version="labkit " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("map", help="研究フォルダ全体の地図を作る")
    p.add_argument("dir")
    p = sub.add_parser("init", help="実験プロジェクトの雛形を作る")
    p.add_argument("dir")
    p.add_argument("--name")
    p.add_argument("--sample", action="store_true", help="練習用の合成 DSC データを DATA/ に入れる")
    p = sub.add_parser("demo", help="雛形 + 練習データ + 見本の解析 + ギャラリー")
    p.add_argument("dir")

    for name, hlp in (("ledger", "台帳を作り直す"), ("index", "解析の一覧を作り直す"),
                      ("gallery", "ギャラリーとビューアを作り直す"), ("refresh", "台帳・一覧・ギャラリーをまとめて")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--root")
    p = sub.add_parser("trace", help="解析の根拠を生データまで辿る")
    p.add_argument("ana_id")
    p.add_argument("--root")
    p = sub.add_parser("new", help="解析フォルダを作る")
    p.add_argument("slug")
    p.add_argument("-q", "--question", required=True)
    p.add_argument("--where", nargs="*", default=[], help="列=値 で台帳を絞る（例: instr=dsc sample=PPP）")
    p.add_argument("--procedure", default="")
    p.add_argument("--supersedes")
    p.add_argument("--root")
    for name in ("manuscript", "talk"):
        p = sub.add_parser(name, help="論文の作業フォルダ" if name == "manuscript" else "発表の作業フォルダ")
        p.add_argument("slug")
        p.add_argument("--title")
        p.add_argument("--root")

    a = ap.parse_args(argv)

    if a.cmd == "map":
        dest, made, skipped = scaffold.research_map(a.dir)
        _report(dest, made, skipped)
        print("\n~/.claude/CLAUDE.md に次の内容を足すと、Claude がこの地図を読むようになる（%s/CLAUDE_snippet.md）:\n"
              % dest)
        with open(os.path.join(dest, "CLAUDE_snippet.md"), encoding="utf-8") as f:
            print(f.read())
    elif a.cmd in ("init", "demo"):
        sample = a.cmd == "demo" or a.sample
        dest, made, skipped = scaffold.init_project(a.dir, getattr(a, "name", None), sample=sample)
        _report(dest, made, skipped)
        _refresh(dest)
        if a.cmd == "demo":
            # インストールせずに clone から動かしたときも、見本のスクリプトが labkit を import できるように
            env = dict(os.environ)
            pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env["PYTHONPATH"] = pkg_parent + os.pathsep + env.get("PYTHONPATH", "")
            for s in ("ExampleFat-A", "ExampleFat-B"):
                subprocess.run([sys.executable, os.path.join(dest, "tools", "example_analysis.py"), "--sample", s],
                               cwd=dest, check=True, env=env)
            print("\n開いてみる: %s" % os.path.join(dest, "reports", "figure_gallery.html"))
            print("根拠を辿る: cd %s && labkit trace <ana_id>" % dest)
    elif a.cmd == "ledger":
        build_ledger.build(_root(a))
    elif a.cmd == "index":
        print(analysis.build_index(_root(a)))
    elif a.cmd == "gallery":
        gallery.build(_root(a))
    elif a.cmd == "refresh":
        _refresh(_root(a))
    elif a.cmd == "trace":
        print(json.dumps(analysis.trace(_root(a), a.ana_id), ensure_ascii=False, indent=2))
    elif a.cmd == "new":
        L = ledger.load(_root(a))
        conds = dict(w.split("=", 1) for w in a.where)
        rows = L.select(**conds)
        A = analysis.new(L, a.slug, question=a.question, inputs=rows, procedure=a.procedure,
                         supersedes=a.supersedes)
        print("%s（入力 %d 測定）-> %s" % (A.ana_id, len(rows), A.dir))
    elif a.cmd in ("manuscript", "talk"):
        fn = scaffold.new_manuscript if a.cmd == "manuscript" else scaffold.new_talk
        dest, made, skipped = fn(_root(a), a.slug, a.title)
        _report(dest, made, skipped)


if __name__ == "__main__":
    main()
