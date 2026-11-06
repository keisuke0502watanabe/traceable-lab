# {{name}} — データの置き場所と約束

{{date}} に `labkit init` で作った。半年後の自分と、あとから来る人のために。

```
{{name}}/
  DATA/                凍結層。置いたら動かさない・名前を変えない。新しい測定は装置/年-月で足す
  ledger.csv           測定台帳。一行 = 一測定（labkit ledger が生成。手書きの列は残る）
  ledger_gaps.csv      日付・試料・熱履歴のどれかが機械で埋まらなかった行（生成物）
  ledger_fixes.csv     DATA を触らずに値を直す表（meas_id, column, value, reason）
  analyses/            解析。一問い = 一フォルダ（ana-YYYYMMDD-slug）。平ら。消さない
  analyses_index.csv   全 manifest の一覧（生成物）
  reports/             人に見せるもの。figure_gallery.html と analyses_viewer.html は生成物
  Documents/           論文の作業フォルダ（labkit manuscript <名前> で作る）
  notes/               日付ごとの短い日誌と、申し送り（HANDOFF）
  scratch/             試行錯誤の場所。月に一度空にしてよい
  tools/               このプロジェクト専用のスクリプト（readers.py = 自分の装置の形式）
  labkit.json          プロジェクトの設定（名前・試料名の言い換え）
```

## 二つの禁止

1. **DATA/ に触らない。** 分類したくなったら `ledger.csv` の `status` / `tags` / `note` を書き換える。
   フォルダを動かすと `path` が壊れ、過去の解析の根拠が失われる。値が間違っていたら `ledger_fixes.csv` に理由つきで書く。
2. **analyses/ を消さない。** 失敗は `status: rejected` として残す。やり直しは `supersedes` に前の ana_id を入れて新しく作る。

この二つは、別のチャット・別のツール・別の人が作業するときも同じ。

## 二種類の ID

- `meas_id` — 測定。`ledger.csv` の一行。ファイルの中身（測定日時・走査番号）から決まるので、ファイルが増えても変わらない。
  例: `dsc-20250414-095225`, `xrd-20250613-143901`
- `ana_id` — 解析。`analyses/` の一フォルダ。例: `ana-20250914-fat-a-ta-scan`

測定と解析は多対多。対応は `manifest.json` の `inputs`（meas_id の配列）が持つ。

## 根拠を辿る鎖

レポートの図 → 脚注の `ana_id` → `manifest.inputs` → `meas_id` → `ledger.csv` の `path` → `DATA/` のファイル

```bash
labkit trace ana-20250914-fat-a-ta-scan
```

## 台帳の列

固定する三列: `meas_id` · `path` · `thermal_history`。それ以外は増やしても組み替えてもよい。
手で書く三列: `status`（ok / bad …）· `tags` · `note`。再生成しても残る。
`sample` / `thermal_history` / `mass_mg` / `Ta_C` は、機械で埋まらなかったときに手で書いた値が残る。

熱履歴の記法: `25→80@10 > hold80/5min > 80→20@10 > hold20/30min > 20→80@5`
（`A→B@rate` は昇降温 °C/min、`holdT/Nmin` は等温保持）

`Ta_C` は「冷却のあとの最長の保持」という目安で入れている。信用しすぎない。

## いつもの流れ

```python
from labkit import ledger, analysis
L = ledger.load()
rows = L.select(instr="dsc", sample="ExampleFat-A", status=lambda s: s != "bad")
A = analysis.new(L, "fat-a-ta-scan", question="…", inputs=rows,
                 procedure="tools/example_analysis.py", params={})
# … 計算。図は A.out("tm_vs_ta.svg") に。図の隅に ana_id を刻む
A.finish(results={"n_runs": len(rows)}, status="used")      # used / tried / rejected
```

**解析を足したら、最後に必ず** `labkit refresh`（台帳 → 一覧 → ギャラリーとビューア → 点検の要約）。

人に見せた図・レポートは `reports/index.csv` に行を足す（どこに出したか = `used_for`）。

## 検証

二段に分ける。

1. **機械の点検** `labkit check`（読むだけ。`reports/check_report.md`）。解析を作った時点の指紋（入力ファイルの sha1、
   台帳の値、スクリプトの sha1）といまを比べて、DATA の書き換え・台帳の修正・スクリプトの変更・置き換え済みの版の引用・
   上流の誤り・0 バイトのファイル・検証の記録が無い used を拾う
2. **数値の検算** `labkit audit <名前>` で点検メモを作り、生データから別のコードで出し直して比べる。
   点検中は何も直さない。誤り／要注意／問題なし／見ていないもの に分けて書く

結果は `labkit verify <ana_id> --result ok|caution|error --method "…"` で解析に残す（ギャラリーに印が出る）。
直したら `labkit downstream <ana_id|スクリプト>` の順に作り直す。

## 決めごと（規約）の記録

閾値・基準・記号などを決めたら、ここに日付と根拠の ana_id を一行で足す。

- （例）{{date}}: 誘導時間の閾値は X = 5 %。根拠 ana-YYYYMMDD-…
