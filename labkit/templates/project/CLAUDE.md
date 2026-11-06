# {{name}} — Claude への申し送り

最初に `README.md`（このプロジェクトの約束）と、`notes/` の最新の日誌・HANDOFF を読むこと。

## 守ること

- `DATA/` のファイルを動かさない・名前を変えない・書き込まない。値の誤りは `ledger_fixes.csv` に理由つきで書く
- `analyses/` のフォルダを消さない。失敗は `status: rejected`、やり直しは `supersedes` つきで新しく作る
- 解析は必ず `labkit.analysis.new(...)` でフォルダを作ってから始め、図は `A.out(...)` に保存する。
  試すだけの計算は `scratch/` で行う
- 生データのパスを手で書かない。`labkit.ledger` の `select` と `resolve` を通す
- 図には出どころ（ana_id）を小さく刻む
- 解析を足したら最後に `labkit refresh` を回す（ギャラリーとビューアの更新）
- ファイルやフォルダを動かすときは、先に提案して承認をもらう
- 生成物（台帳・ギャラリー・スライドの .pptx/.html・論文の図の出力）を直接編集しない。元を直して作り直す

## 検証

- 解析を used にする前と、論文・発表に出す前に `labkit check` を回し、誤り・要注意をユーザーに見せる
- 数値の正しさを確かめるときは skill `verify-analysis` に従う。点検中は何も直さない（読むだけ）。
  生データから別のコードで出し直して比べ、誤り／要注意／問題なし／見ていないもの に分けて `notes/audit-*.md` に書く
- 確かめた結果は `labkit verify <ana_id> --result ok|caution|error --method "…"` で残す
- 直したら `labkit downstream <直したもの>` の順に作り直す（新しい版は supersedes つき、古い版は rejected）

## 日誌

作業の区切りごとに `notes/YYYY-MM-DD.md` に追記する。回した ana_id、分かったこと 1–3 行、捨てた方向、次にやること。
ユーザーの指示は「ユーザー『…』」と短く引用して、誰の判断かを残す。

## skill

`.claude/skills/` に、このプロジェクトでよく使う手順がある（新しい解析・検証・日誌・申し送り・図の根拠を辿る）。
