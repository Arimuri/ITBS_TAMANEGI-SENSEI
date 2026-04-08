# composition_advisor

有村の学習用に、複数パートの MIDI を投げると **コード進行・度数・声部の問題点** を検出して、必要なら Claude に投げて自然言語の添削まで返してくれるツール。

Studio One で作曲した複数 MIDI ファイル(melody.mid, chord.mid, bass.mid …)を想定しています。

---

## できること

```
複数の .mid ファイル
  ↓
1. music21 でパース → 内部モデル(pydantic)に正規化
2. 拍ごとの Slice(垂直方向の音集合)を生成
3. 各 Slice にコード/度数/最低音を付与
4. ルールベースで「気になる箇所」を検出
   - 半音衝突 (semitone_clash)
   - 声部交叉 (voice_crossing)
   - bass 楽器より低い音 (bass_below)
   - 平行5度・平行8度 (parallel_motion)
   - 音域逸脱 (range_check)
   - コードトーン外 (chord_tone_check)
5. (任意) Claude に投げて自然言語の添削を生成
```

## インストール

Python 3.12 以上。`uv` を使うのがおすすめ。

```bash
cd composition_advisor
uv sync
```

## 使い方

### テキスト出力(コード/度数 + ルール検出結果)

```bash
uv run analyze melody.mid chord.mid bass.mid --key C
```

### JSON 出力(中間表現すべて)

```bash
uv run analyze *.mid --key C --output json > result.json
```

### LLM プロンプトだけ確認(API キー不要)

```bash
uv run analyze *.mid --key C --output prompt
```

### Claude に投げて自然言語の添削を生成

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run analyze *.mid --key C --llm
# モデル指定:
uv run analyze *.mid --key C --llm --model claude-sonnet-4-6
```

### ジャンル設定でルールをカスタマイズ

```bash
uv run analyze *.mid --key C --config examples/jazz.yaml
```

`examples/jazz.yaml` では `parallel_motion` を無効化し、`voice_crossing` `chord_tone_check` を `info` 重大度に下げています。

### 特定の小節範囲だけ分析

```bash
uv run analyze *.mid --key C --bars 4-8     # bar 4-8 のみ
uv run analyze *.mid --key C --bars 4       # bar 4 だけ
uv run analyze *.mid --key C --bars 4-      # bar 4 以降
uv run analyze *.mid --key C --bars -8      # 曲頭から bar 8 まで
```

## 設定ファイル(yaml)

```yaml
genre: jazz
key: C       # 任意。--key より弱い

rules:
  semitone_clash:
    enabled: true
    severity: warning   # info | warning | error
  parallel_motion:
    enabled: false
  chord_tone_check:
    enabled: true
    severity: info
```

各ルールキーの下に書ける項目:
- `enabled` (bool, default true) — false にすればそのルールはスキップ
- `severity` (str, optional) — そのルールが出す Issue の severity を上書き
- ルール固有のパラメータ(下記参照)— params dict としてルールに渡される

ルール固有パラメータ:
- `semitone_clash.ignore_durations_below` (float beats, default 0.0) — この秒数より短い重なりは無視(MIDIクオンタイズ揺れ対策)
- `chord_tone_check.ignore_durations_below` (float beats, default 0.25) — この秒数より短い音は通過音として無視
- `chord_tone_check.harmony_keywords` (list[str]) — ハーモニー側パートとみなすキーワード(default: chord/comp/piano/synth/pad/keys/bass…)
- `chord_tone_check.target_parts` (list[str]) — チェック対象パート名を明示指定(default: harmony 以外を自動検出)

## 開発

### テスト

```bash
uv run pytest
```

### テスト用 MIDI フィクスチャの再生成

```bash
uv run python tests/fixtures/_make_simple.py     # I-V-vi-IV in C
uv run python tests/fixtures/_make_clash.py      # parallel 5th + clash + crossing
```

### ディレクトリ構成

```
composition_advisor/
├── composition_advisor/
│   ├── io/         # MIDI 読み込み + 内部モデル正規化
│   ├── model/      # pydantic モデル(Score / Slice / Issue)
│   ├── analyze/    # コード/調/度数/Slice 抽出
│   ├── critique/   # ルールベースの問題検出 + 設定
│   │   ├── rules/  # 個別ルール
│   │   ├── runner.py
│   │   └── config.py
│   ├── llm/        # Claude API 連携
│   └── cli.py      # typer ベース CLI
├── examples/
│   ├── minimal.py
│   └── jazz.yaml
└── tests/
    ├── fixtures/   # _make_*.py で再生成可
    └── test_rules.py
```

## 既知の制約

- **MIDI 入力ではエンハーモニック情報が失われる**(F♯ と G♭ を区別できない)。MusicXML 対応は将来課題。
- **chordify() は遅い**。大規模スコアでは数秒〜数十秒かかることがあります。
- 表示は **Studio One 表記(中央 C = C3)** に統一しています。music21 内部の C4 とは1オクターブずれます。
- 曲中の拍子変化は music21 の measure offset を直接見るので追従します(同じ曲内で 4/4 → 3/4 などしてもbar/beatは正しく出ます)。
