"""雛形の生成 → 台帳 → 解析 → ギャラリー → trace を一通り通すテスト（標準ライブラリのみ）。

    python3 -m unittest discover -s tests
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from labkit import analysis, build_ledger, gallery, ledger, scaffold  # noqa: E402


def run(*args, cwd=None):
    env = dict(os.environ, PYTHONPATH=REPO)
    return subprocess.run([sys.executable, "-m", "labkit", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=True)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "demo")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_demo(self):
        run("demo", self.proj)
        L = ledger.load(self.proj)
        self.assertEqual(len(L), 8)
        # バックアップのコピーは行を持たず duplicates に入る
        dup = L.get("dsc-20250414-113002")
        self.assertIn("backup/", dup["duplicates"])
        # ledger_fixes.csv の値で上書きされる
        self.assertEqual(L.get("dsc-20250415-122040")["mass_mg"], "4.06")
        # 試料名の空欄は gaps に出る
        self.assertEqual(L.get("dsc-20250502-150256")["gaps"], "sample")
        # 熱履歴と Ta
        r = L.get("dsc-20250414-095225")
        self.assertEqual(r["thermal_history"], "25→80@10 > hold80/5min > 80→20@10 > hold20/30min > 20→80@5")
        self.assertEqual(r["Ta_C"], "20")

        items = analysis.list_all(self.proj)
        self.assertEqual(len(items), 2)
        A = items[0]
        self.assertEqual(A.manifest["status"], "used")
        self.assertIn("t_peak_vs_Ta.svg", A.manifest["outputs"])
        t = analysis.trace(self.proj, A.ana_id)
        self.assertTrue(all(i["path"].startswith("DATA/") for i in t["inputs"]))

        with open(os.path.join(self.proj, "reports", "figure_gallery.html"), encoding="utf-8") as f:
            self.assertIn(A.ana_id, f.read())

    def test_manual_columns_survive_rebuild(self):
        scaffold.init_project(self.proj, sample=True)
        build_ledger.build(self.proj, quiet=True)
        p = os.path.join(self.proj, "ledger.csv")
        with open(p, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            cols = list(rows[0].keys())
        rows[0]["status"] = "bad"
        rows[0]["note"] = "パンの蓋が浮いた"
        target = rows[0]["meas_id"]
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        build_ledger.build(self.proj, quiet=True)
        r = ledger.load(self.proj).get(target)
        self.assertEqual((r["status"], r["note"]), ("bad", "パンの蓋が浮いた"))

    def test_init_does_not_overwrite(self):
        os.makedirs(self.proj)
        with open(os.path.join(self.proj, "README.md"), "w", encoding="utf-8") as f:
            f.write("自分の README")
        _, made, skipped = scaffold.init_project(self.proj)
        self.assertIn("README.md", skipped)
        with open(os.path.join(self.proj, "README.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "自分の README")

    def test_manuscript_talk_map(self):
        scaffold.init_project(self.proj)
        d, made, _ = scaffold.new_manuscript(self.proj, "Polymorph Kinetics", "多形の速度論")
        self.assertTrue(d.endswith("manuscript-polymorph-kinetics"))
        self.assertIn("PROGRESS.md", made)
        d, made, _ = scaffold.new_talk(self.proj, "conf-2025")
        self.assertTrue(os.path.exists(os.path.join(d, "src", "facts.md")))
        d, made, _ = scaffold.research_map(os.path.join(self.tmp, "Research"))
        self.assertTrue(os.path.isdir(os.path.join(d, "4-データ")))
        self.assertIn("MOVES.md", made)

    def test_supersedes_lineage(self):
        run("demo", self.proj)
        L = ledger.load(self.proj)
        first = analysis.list_all(self.proj)[0]
        B = analysis.new(L, "redo", question="やり直し", inputs=first.manifest["inputs"],
                         procedure="test", supersedes=first.ana_id)
        B.finish(status="tried")
        first.finish(status="rejected", note="t0 の取り方を間違えた")
        analysis.build_index(self.proj)
        data = gallery.collect(self.proj)
        rec = {a["id"]: a for a in data["analyses"]}
        self.assertEqual(rec[first.ana_id]["superseded_by"], B.ana_id)
        self.assertEqual(rec[first.ana_id]["lineage"], rec[B.ana_id]["lineage"])


if __name__ == "__main__":
    unittest.main()
