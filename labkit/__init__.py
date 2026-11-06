"""labkit — 図から生データまで辿れる研究フォルダを作り、回すための小さな道具箱。

- ``labkit.ledger``    測定台帳 ledger.csv の読み込みと絞り込み
- ``labkit.analysis``  解析フォルダ analyses/ana-YYYYMMDD-slug/ と manifest.json
- ``labkit.build_ledger``  DATA/ を読んで台帳を作り直す（手書きの列は残す）
- ``labkit.gallery``   図ギャラリーと解析ビューア（HTML）を生成
- ``labkit.scaffold``  プロジェクト・論文・発表の雛形を作る

標準ライブラリだけで動く。コマンドは ``labkit --help``（または ``python3 -m labkit --help``）。
"""
__version__ = "0.1.0"
