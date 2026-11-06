# 申し送り — {{title}}

## §0 次のチャットはここから

- 出ている成果物: （例: talk-v3.pptx / .pdf）
- 作業中:
- 誤りが分かっているもの:
- 持ち時間: いまの構成で __:__ / __:__ 枠

## §1 どこに何があるか

```
talk-{{slug}}/
  START-HERE.md
  handover.md        ← このファイル
  ref.md             過去の発表から使ったスライドの正本の場所（コピーしない）
  src/
    content.md       スライドの本文と図の指定（直すのはここ）
    facts.md         数値の正本（根拠の ana_id つき）
    notation.md      記号・色の取り決め
    figs/            スライド専用の図のスクリプト（データは analyses/ から読む）
  out/               出力（生成物）
  old/               古い版
```

## §2 作り方

（使うツールに合わせて書く。例: Claude に「content.md から v4 をビルドして」、Marp、python-pptx、Keynote への手作業 …）

## §3 構成

| # | タイトル | 言うこと | 図（ana_id） | 秒 |
|---|---|---|---|---|
| 1 | | | | |
