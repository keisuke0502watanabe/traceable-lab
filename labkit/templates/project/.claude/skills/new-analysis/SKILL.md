---
name: new-analysis
description: このプロジェクトで新しい解析を始めるときの手順。台帳から測定を選び、analyses/ にフォルダを作り、図と結果を残し、ギャラリーを更新する。「解析して」「〜を比べて」「〜の図を作って」と頼まれたら使う。
---

# 新しい解析を始める

1. **問いを一文にする。** 「Ta が誘導時間をどう決めるか」のように。曖昧なら作業前にユーザーに確かめる。
2. **台帳から測定を選ぶ。** パスを手で書かない。
   ```python
   from labkit import ledger, analysis
   L = ledger.load()
   rows = L.select(instr="dsc", sample="…", status=lambda s: s != "bad")
   ```
   選んだ行数と、除いた行（status が bad、gaps がある、など）をユーザーに報告する。
3. **同じ問いの解析が既にないか見る。** `analyses_index.csv` を語句で探す。続きなら `supersedes=<前の ana_id>`。
4. **フォルダを作る。**
   ```python
   A = analysis.new(L, "<短い英語の slug>", question="<一文>", inputs=rows,
                    procedure="<スクリプトのパスか関数名>", params={...}, supersedes=None)
   ```
5. **計算する。** スクリプトは解析フォルダの中か `tools/` に置き、manifest の procedure に書く。
   図は `A.out("名前.png|svg")` に保存し、図の隅に `A.ana_id` を刻む（`labkit.svgplot.plot(..., stamp=A.ana_id)`）。
   表は CSV で `out/` に。
6. **終える。** `A.finish(results={要約の数値}, status="used"|"tried"|"rejected")`。
   `notes.md` の「分かったこと」「次」を数行で埋める。rejected なら理由を必ず書く。
7. **更新する。** `labkit refresh`。
8. **日誌に一行。** `notes/YYYY-MM-DD.md` に ana_id と結論。

## 報告の仕方

- 数値は単位と、どの規約で出したか（閾値・当てはめ範囲）と一緒に書く
- 図は ana_id と一緒に示す
- 規約を新しく決めた場合は README の「決めごと」に一行足すことを提案する
