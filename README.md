# ITBS_TAMANEGI-SENSEI

有村の音楽学習用ツール置き場。

## 中身

### [composition_advisor/](composition_advisor/)

複数パートの MIDI を投げると、コード進行・度数・声部の問題点を検出して、必要なら Claude に投げて自然言語の添削まで返してくれるツール。

詳細は [composition_advisor/README.md](composition_advisor/README.md) を参照。

```bash
cd composition_advisor
uv sync
uv run analyze tests/fixtures/simple_*.mid --key C
```
