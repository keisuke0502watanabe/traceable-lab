# traceable-lab

**論文の図から、生データまで辿れる研究フォルダ**を、コマンド一つで手元に作るための道具箱（`labkit`）。

教習ページ（仕組みの考え方）: https://keisuke0502watanabe.github.io/traceable-lab/

DSC・XRD・SAXS などの測定が増え続ける研究室で、一年近く運用した仕組みを一般化したものです。
半年後に「この図はどの測定から、どの条件で描いたのか」と聞かれても、すぐ答えられるようにします。

```
論文・スライドの図 → 解析フォルダ（ana_id）→ manifest.json の inputs → 測定台帳（meas_id）→ DATA/ の生ファイル
```

- 標準ライブラリだけで動く（Python 3.9 以上。numpy も matplotlib も不要）
- 台帳とギャラリーは何度でも作り直せる生成物。手で書いた列（status・tags・note）は残る
- Claude Code 用の `CLAUDE.md` と skill（新しい解析・日誌・申し送り・図の根拠を辿る）つき。Claude を使わなくても仕組みはそのまま使える

## 入れ方

```bash
pip install git+https://github.com/keisuke0502watanabe/traceable-lab
```

入れずに使うなら clone して `python3 -m labkit …`。

## まず試す（5 秒）

```bash
labkit demo my-demo
open my-demo/reports/figure_gallery.html      # macOS。Windows は start、Linux は xdg-open
```

練習用の合成 DSC データ（8 測定。バックアップのコピー・試料名の入れ忘れ・質量の打ち間違いをわざと含む）から、
台帳 → 見本の解析 2 本 → 図ギャラリーと解析ビューアまでを作ります。中のデータは作りものです。

```bash
cd my-demo
labkit trace ana-YYYYMMDD-examplefat-a-ta-scan   # 図の根拠を生データまで辿る
```

## 自分の研究で使う

```bash
labkit map ~/Research                 # 研究フォルダ全体の地図（0-受け皿 … 9-アーカイブ、README、MOVES）
labkit init ~/Research/4-データ/my-project
# DATA/ に測定ファイルを置く（置いたら動かさない）
cd ~/Research/4-データ/my-project
labkit ledger                         # 台帳を作る
labkit new ta-scan -q "Ta が誘導時間をどう決めるか" --where instr=dsc sample=PPP
# … 解析（Python からは labkit.ledger / labkit.analysis）
labkit refresh                        # 台帳 → 解析の一覧 → ギャラリーとビューア
labkit manuscript paper1 --title "…"  # 論文の作業フォルダ
labkit talk conf-2026 --title "…"     # 発表の作業フォルダ
```

作られるプロジェクト:

```
my-project/
  DATA/                凍結層（置いたら動かさない）
  ledger.csv           測定台帳。一行 = 一測定（生成物）
  ledger_gaps.csv      日付・試料・熱履歴が埋まらなかった行（手で埋める宿題）
  ledger_fixes.csv     DATA を触らずに値を直す表（meas_id, column, value, reason）
  analyses/            一問い = 一フォルダ（manifest.json・notes.md・out/）。消さない
  analyses_index.csv   解析の一覧（生成物）
  reports/             figure_gallery.html・analyses_viewer.html（生成物）、index.csv、talk-*/
  Documents/           manuscript-*/（PROGRESS.md、outline、draft、figs/、comments/、lit/、share/）
  notes/               日誌と申し送り（HANDOFF）
  scratch/  tools/     試行錯誤と、このプロジェクト専用のスクリプト（readers.py）
  README.md  CLAUDE.md  .claude/skills/  labkit.json
```

## 台帳が読める形式

| 形式 | 読むもの |
|---|---|
| PerkinElmer Pyris の .txt 書き出し（DSC） | 測定日時、試料名、質量、実験者、Method Steps → 熱履歴 `25→80@10 > hold80/5min > …`、保持温度 Ta |
| Rigaku の .ras（XRD） | 走査の開始時刻、試料名、雰囲気温度 |

ほかの形式は、プロジェクトの `tools/readers.py` に reader（ファイル 1 本 → 台帳の 1 行を返す関数）を書けば台帳に入ります。
雛形に 2 列 CSV の例があります。meas_id はファイル名ではなく、ファイルの中身（測定日時・走査番号）から決めてください。

## Python から

```python
from labkit import ledger, analysis, svgplot

L = ledger.load()                                    # cwd から上へ ledger.csv を探す
rows = L.select(instr="dsc", sample="PPP", Ta_C=(30, 50), status=lambda s: s != "bad")
A = analysis.new(L, "ppp-avrami", question="…", inputs=rows,
                 procedure="tools/my_script.py", params={"t0": "induction"})
for r in rows:
    path = L.resolve(r)                              # 生ファイルの絶対パス
    ...
svgplot.plot(A.out("fig.svg"), [{"x": [...], "y": [...]}], stamp=A.ana_id)   # 図の隅に ana_id
A.finish(results={"n": 2.8}, status="used")          # used / tried / rejected
```

やり直しは `analysis.new(..., supersedes="<前の ana_id>")`。前の解析は消さずに `status="rejected"` と理由を残します。

## 検証

解析が数百になると、コードの小さな誤り（並び順、補間で埋めた値、片側だけの条件、途中で止めた測定 …）が
下流の図や論文の数値にそのまま流れます。検証は二段に分けます。

**1. 機械の点検（読むだけ）**

```bash
labkit check            # reports/check_report.md。--strict で誤りがあれば終了コード 1
```

解析を作った時点で manifest に残した指紋（入力ファイルの sha1、台帳の値、スクリプトの sha1）と、いまを比べます。

| 種類 | 何を見つけるか |
|---|---|
| `data_changed` / `data_missing` | 凍結したはずの生データが書き換わった・消えた |
| `zero_byte` / `unread_files` | 0 バイトのファイル、台帳に入らなかったファイル（黙って抜けない） |
| `ledger_changed` | 解析のあとで台帳の値が変わった（質量の修正、status: bad） |
| `code_changed` | 解析のあとでスクリプトが直された |
| `superseded_used` | 置き換え済みの版が used のまま（古い版を引用していないか） |
| `upstream_*` / `downstream_of_error` | 上流（based_on）が rejected・置き換え済み・誤りあり |
| `check_error` / `unverified` | 検証で誤りが記録された解析、検証の記録が無い used |

**2. 数値の検算（人と Claude）**

```bash
labkit audit segments   # 点検メモの雛形 notes/audit-segments_<日付>.md
```

点検中は何も直さず、生データから別のコードで数値を出し直して出力と比べ、誤り／要注意／問題なし／見ていないもの に分けて書きます。
Claude には skill `verify-analysis` があります。結果は解析に残します。

```bash
labkit verify ana-…-ta-scan --result error --method "生データから段の境界を出し直した" --note "途中で止めたランで境界がずれる"
labkit downstream tools/segments.py        # 直したら作り直す解析を、上流から順に
```

ギャラリーとビューアに「検証済み／要注意／誤りあり」と「置き換え済み」の印が出ます。

## 五つの約束

1. 生データは凍結する（動かさない・名前を変えない）
2. 一行が一測定の台帳を持つ（生データから作り直せる）
3. 一つの問いに一つの解析フォルダ
4. 消さずに、状態（used / tried / rejected）で残す
5. 生成物（台帳・ギャラリー・スライド・論文の図）は手で直さず、元を直して作り直す

## テスト

```bash
python3 -m unittest discover -s tests
```

## ライセンス

MIT
