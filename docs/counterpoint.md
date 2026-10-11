# 対位法トレーナー

既存の `composition_advisor` に加えた、個人用の第1〜5種・2声練習画面です。正解例との一致ではなく、明文化した規則への適合を調べます。点数による音楽的価値の判定や、LLMによる採点は行いません。

## 起動

Python 3.12以上、uv、Node.js 22/24 LTS、npmを使います。依存の取得時だけインターネット接続が必要です。起動後の練習・採点にはAPIキーも外部通信も不要です。

```bash
# リポジトリ直下から
cd composition_advisor
uv sync --extra web --frozen
cd ../web
npm ci
npm run build
cd ..
sh scripts/start-counterpoint.sh
```

http://127.0.0.1:8000 を開きます。サーバーは既定でこのPCからだけ接続できる設定です。ポートを変える場合は `sh scripts/start-counterpoint.sh --port 8001`。終了は Ctrl+C です。

`uv` がない場合は [uv公式インストール手順](https://docs.astral.sh/uv/getting-started/installation/) を参照してください。壊れた既存環境を残したい場合、`composition_advisor/` で `UV_PROJECT_ENVIRONMENT=../.venv-counterpoint uv sync --extra web --frozen` を使います。起動スクリプトはその専用環境を優先します。

### 開発時

2つのターミナルで以下を実行します。

```bash
# ターミナル1: リポジトリ直下から
cd composition_advisor
uv run --extra web --frozen counterpoint

# ターミナル2: リポジトリ直下から
cd web
npm ci
npm run dev
```

http://127.0.0.1:5173 のVite開発画面が、8000のAPIへ同一オリジンのプロキシ経由で接続します。本番ビルド後はPythonが `web/dist` を配信するため、Nodeサーバーは不要です。別配置では `COUNTERPOINT_WEB_DIST` にビルド済みディレクトリを指定できます。標準手順はリポジトリのチェックアウトからの実行です。

## 練習の流れ

1. 第1〜5種から課題を選び、冒頭の「この課題の進め方」で目的・リズム・主なルールを確認します。
2. ピアノロールの入力可能な音高をクリックして対旋律を書きます。第1種は全音符、第2種は半音符、第3種は四分音符、第4種は弱拍から小節を跨ぐ保持音、第5種は指定された混合リズムです。同じ入力枠への入力は置換になります。固定休符には音を置けません。
3. 音符を選んでドラッグすると音高を変更できます。削除、Undo、Redoも使えます。定旋律は固定です。
4. 五線譜は同じデータから即時更新されます。表示切替で「同期」「ピアノロールのみ」「五線譜のみ」を選べます。五線譜は閲覧・選択用で、直接入力には対応しません。
5. 再生・停止、テンポ、声部別ミュートで各旋律と2声を確認します。
6. 提出すると、入力の完成状態、規則違反と警告の件数、日本語の理由を表示します。指摘を選ぶと関係する音符を両表示で確認できます。ヒントは必要なときに開きます。
7. 修正すると、直前の添削は「変更前の結果」として扱います。再提出して確認してください。
8. 回答と提出履歴はブラウザに自動保存されます。別の試行として解き直すこともできます。

中央CはMIDI 60、内部と五線譜はC4です。ピアノロールのStudio One表記ではC3になります。これは表示名の差で、譜面や再生を移調しません。

## 保存と履歴

保存先はそのブラウザ・そのオリジンのlocalStorageです。スキーマにバージョンを持ち、課題ごとの入力中の回答と、提出時の回答・結果を分けて保存します。提出日時、試行ID、提出回数、開いたヒント、ルールとエンジンのバージョンを残します。

公開版では同じログインを使う端末間で**提出済みの履歴**を自動同期します。初回アクセス時に既存のブラウザ内履歴も取り込み、同じ提出IDを重複保存しません。ヒント利用は両端末で開いた段階の大きい方を残します。提出時・画面へ戻った時・接続回復時・表示中の約1分ごとに同期し、「履歴を同期」ボタンでも更新できます。失敗時は端末の履歴を保持して再試行し、状態を左下に表示します。

**入力中の回答と退避した未提出回答は端末ごと**です。履歴の「この回答から新しい試行」で別端末の回答を開いて続けられます。新試行・履歴復元の直前の入力は「この端末に退避した回答」に残すため、同期や復元で編集中の音符を消しません。ブラウザのサイトデータを削除すると未提出回答は失われます。提出済みでも「同期済み」を確認するまではサイトデータを消さないでください。

同じブラウザで複数タブを開いた場合、保存される入力中の回答は最後に操作したタブのものです。提出履歴はタブ間で追加統合され、他のタブやサーバーから届いた履歴が、保存済みの回答を置き換えることはありません。

ローカルの標準起動は従来どおりブラウザ内保存のみです。同期を有効にするには `COMPOSITION_ADVISOR_USER` と `COMPOSITION_ADVISOR_PASSWORD` の両方、および `COUNTERPOINT_HISTORY_DB`（永続SQLiteファイルのパス）を環境変数で指定します。認証なしの共有DBは開きません。公開版の保存・バックアップ先は [デプロイ手順](deployment.md) を参照してください。能動作業時間の計測・外部ストレージへの自動バックアップは未実装です。

## 採点と初期範囲

対象は4/4・長調・2声の第1〜5種です。課題が指定する声部と固定リズムに音高を入力します。第5種は自由なリズム作曲全体を扱うものではなく、半音符・四分音符・保持音などを組み合わせた課題です。入力できる音は課題の調と音域に合わせて絞ってあり、異名同音の手動再綴りは行いません。綴りを保存し、音高だけに還元せず協和を判定します。

第1種のv1採点と過去の履歴を維持し、第2〜5種は拍・経過音・刺繍音・掛留を検査するv2プロファイルで採点します。判定する項目、例外、警告への分類、教材との違いは [第1種の採点方針](counterpoint-theory.md) と [第2〜5種の採点方針](counterpoint-species.md) を参照してください。特定のフックス教材の完全再現を名乗らない学習用プロファイルです。

未入力は合格にしません。合格は入力が完成し、規則違反が0件の場合です。警告が残る場合は件数も示します。音楽としての点数は付けません。同じ入力とプロファイルで同じ結果になります。古い結果は変更後の回答の評価として扱いません。

## 構成と既存機能との関係

- `composition_advisor/composition_advisor/counterpoint/`: 綴り付きPydanticモデル、整数tick、独立した規則とバージョン付き教材。検証用解答は公開APIに含めません。
- `composition_advisor/composition_advisor/api.py`: FastAPIの薄い接続層。課題・規則の読み出し、提出、ビルド済み画面の配信。
- `composition_advisor/composition_advisor/history.py`: ログイン単位のSQLite提出履歴。IDで重複排除し、回答の上書きを拒否。複数端末の追加とヒント利用をトランザクション内で統合。
- `web/src/sync.ts` / `useHistorySync.ts`: 既存ローカル履歴の移行、差分送信・履歴取得、失敗時の再試行。未提出の譜面は同期しません。
- `web/`: React + TypeScript + Vite、SVGピアノロール、VexFlow五線譜、Web Audioによる再生。
- `tests/test_counterpoint*.py` と `web/` のテスト: 採点・API・画面データ・操作の検証。

既存Pythonパッケージ、music21、Pydantic、依存管理を利用します。既存のMIDI由来 `Score` は綴りや安定IDを保持しないため、新しい練習モデルを追加しました。採点は新モデルを正本とし、旧モデルとの変換は今後のMIDI連携時に追加します。既存の `critique/species_runner.py`、ポップス用設定、MIDI入出力、Claude連携、自動修正には手を加えていません。

## 検証コマンド

```bash
cd composition_advisor
uv run --extra web --frozen pytest -q
uv run --frozen analyze --help
uv run --frozen analyze analyze tests/fixtures/simple_*.mid --key C
cd ../web
npm test
npm run build
```

別のターミナルで `sh scripts/start-counterpoint.sh` を起動してから、`web/` で以下を実行します。

```bash
npm run test:e2e
```

ブラウザテストはインストール済みのGoogle Chromeを使用します。別ポートでは `COUNTERPOINT_BASE_URL=http://127.0.0.1:8001 npm run test:e2e`。Chromiumを別途利用する場合は `npx playwright install chromium` の後に `PLAYWRIGHT_CHANNEL=chromium npm run test:e2e` を指定します。個人用のChromeプロファイルは使用しません。

履歴同期のテストは、認証と履歴DBを有効にした別サーバーに対して **2件だけ** 実行します。`trainer.spec.ts` は履歴が空である前提のため、同期サーバーで全件を回すと同じログインに蓄積した履歴を数えて失敗します。

```bash
# ターミナル1（リポジトリ直下）。パスワードはローカル検証用の仮の値でよい
COMPOSITION_ADVISOR_USER=e2e COMPOSITION_ADVISOR_PASSWORD=e2e-local-only \
COUNTERPOINT_HISTORY_DB=/tmp/counterpoint-history-test.sqlite3 sh scripts/start-counterpoint.sh --port 8022
# ターミナル2（web/）
COUNTERPOINT_BASE_URL=http://127.0.0.1:8022 COUNTERPOINT_AUTH_USER=e2e COUNTERPOINT_AUTH_PASSWORD=e2e-local-only \
npx playwright test e2e/history-sync.spec.ts e2e/local-tabs.spec.ts
```

### 実行結果（2026-10-10）

- Python: **284件成功**。既存43件に加え、第1種・第2〜5種の採点、履歴DB、APIのテスト。7課題の検証解答は採点器に加えて理論資料と手計算でも確認しました（[第2〜5種の採点方針](counterpoint-species.md)）。
- フロントエンド単体: **23件成功**。音名・音高・時間・固定ID、Undo/Redo、保存・履歴、履歴の統合、音声開始待ち中の破棄を確認しました。
- Chrome操作: 標準サーバーで **13件成功**（同期テスト1件は自動スキップ）。認証・履歴DB付きサーバーで `history-sync` と `local-tabs` の **2件成功**。入力・ドラッグ・削除・Undo/Redo、表示切替、第2〜5種の固定リズムとタイ、指摘の追跡、ヒント、変更前評価、再提出・履歴、再読み込み、2端末の履歴同期と再送、2タブの履歴統合を確認しました。
- 音声: Chromeの実AudioContextで中央Cの周波数、ミュート、音声時計に沿う再生位置、編集後の音高、提出・編集・課題切替での停止、課題切替時の音声リソース解放、タイの単一発音を確認しました。
- 画面: PC幅1512pxとスマートフォン幅390pxで描画を確認。画面エラー・コンソールエラー・外部へのリクエストは0件でした。五線譜フォントをアプリに同梱しています。
- `npm run build` 成功、`npm audit` で既知の脆弱性0件。既存CLIの起動とサンプルMIDIのJSON解析も成功しました。

実行環境はPython 3.12.2、Node 23.4.0、npm 10.9.2でした。Node 23はVitestの対応系列外の警告が出るため、新規セットアップには上記LTSを使ってください。ほかにStarletteのテストクライアントに外部依存の非推奨警告1件、同梱フォントを含む約1MBのJSバンドルにViteのサイズ警告があります。スピーカーでの聴感、Safari/Firefoxの動作は未検証です。

## 次の拡張

五線譜からの直接入力、第5種の自由リズム・八分音符、MIDI/MusicXML入出力、範囲ループ、試験・コーチモード、LLM解説、自動課題生成、多声・模倣は未実装です。リズム枠は `Exercise.noteSlots`、長く保持する音は小節を跨ぐ単一の音符として扱います。譜面上だけ分割してタイを描き、再生は保持中に再発音しません。

## ライブラリ資料

- [FastAPI: Static Files](https://fastapi.tiangolo.com/tutorial/static-files/) / [Testing](https://fastapi.tiangolo.com/tutorial/testing/): APIと静的画面、テストの構成に参照。
- [uv: Using environments](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path): 専用環境の指定に参照。
- 音楽理論・music21・VexFlowの出典とライセンスは [採点方針・出典](counterpoint-theory.md) を参照。
