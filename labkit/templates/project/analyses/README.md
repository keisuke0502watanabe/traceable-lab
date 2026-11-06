# analyses/ — 一問い = 一フォルダ

```
ana-YYYYMMDD-<slug>/
  manifest.json   機械が読む: question / inputs(meas_id) / procedure / params / results / status / supersedes / based_on
  notes.md        人が読む: 問い・分かったこと・次
  out/            図・表
```

- 作るのは `labkit.analysis.new(...)`、終えるのは `A.finish(results, status)`
- status: `tried`（試した）/ `used`（使った・使える）/ `rejected`（間違い。理由を notes.md に）
- 消さない。やり直しは supersedes つきで新しく作る
- 既にある古いまとめは動かさず `labkit.analysis.register(...)` で manifest だけ置く（external_dir が実体を指す）
