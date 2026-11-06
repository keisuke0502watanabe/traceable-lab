---
name: trace-figure
description: 図・数値・レポートの根拠を生データまで辿り、使った測定に問題がないか確かめる。「この図の根拠は」「Fig. 5 はどの測定から」「この値はどこから」と聞かれたときに使う。
---

# 図の根拠を辿る

1. 図から ana_id を見つける（図の隅の刻印、ファイル名 `<ana_id>__…`、脚注、`reports/index.csv`）。
2. `labkit trace <ana_id>` で inputs（meas_id）と path、熱履歴を出す。
3. 台帳で各 meas_id の `status` / `gaps` / `note` を見る。次を報告する:
   - status が bad の測定が入っていないか
   - gaps（日付・試料・熱履歴の空欄）がある測定
   - `ledger_fixes.csv` で値を直した測定
   - その解析が superseded されていないか（`analyses_index.csv` の superseded_by）
4. `based_on` があれば、元の解析も同じように辿る。
5. 結果を表にして返す: meas_id / 日付 / 試料 / 熱履歴 / status / 注意点。
