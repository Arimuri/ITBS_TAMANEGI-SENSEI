# ITBS_TAMANEGI-SENSEI

有村の音楽学習用ツール置き場。

## 対位法トレーナー

第1〜5種・2声を、ピアノロールで書き、五線譜と音で確認して、日本語の添削を受けるWebアプリです。課題冒頭に短いルール説明があり、公開版では同じログインの端末間で提出履歴を同期します。第5種は指定された混合リズムの練習です。APIキーは不要で、ローカルではログインなしで使えます。

公開版: **https://tamanegi-sensei.intheblueshirt.com/counterpoint/**（既存サイトと同じログイン）。VPSの構成・更新・復旧手順は [docs/deployment.md](docs/deployment.md) を参照してください。

初回セットアップ（Python 3.12以上、uv、Node.js 22/24 LTS、npm）:

```bash
cd composition_advisor
uv sync --extra web --frozen
cd ../web
npm ci
npm run build
cd ..
sh scripts/start-counterpoint.sh
```

**http://127.0.0.1:8000** を開いて使います。終了はターミナルで Ctrl+C。次回はリポジトリ直下で `sh scripts/start-counterpoint.sh` だけで起動できます。

詳しい操作・開発・検証手順は [docs/counterpoint.md](docs/counterpoint.md)、採点方針と出典は [docs/counterpoint-theory.md](docs/counterpoint-theory.md) を参照してください。

既存の `.venv` が別PCのPythonを参照して起動しない場合は、元の環境を残して `UV_PROJECT_ENVIRONMENT=../.venv-counterpoint uv sync --extra web --frozen` を `composition_advisor/` 内で実行できます。起動スクリプトはこの専用環境を優先します。

## 中身

### [composition_advisor/](composition_advisor/)

複数パートの MIDI を投げると、コード進行・度数・声部の問題点を検出して、必要なら Claude に投げて自然言語の添削まで返してくれるツール。

詳細は [composition_advisor/README.md](composition_advisor/README.md) を参照。

```bash
cd composition_advisor
uv sync
uv run analyze analyze tests/fixtures/simple_*.mid --key C
```
