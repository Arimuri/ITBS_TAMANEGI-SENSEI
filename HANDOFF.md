# 引き継ぎメモ — 対位法トレーナー

最終更新: 2026-10-10（Claude Code が Codex から引き継いだ時点の記録。作業の進捗に合わせて更新する）

## Codex へ（次に Codex で再開する場合）

2026-10-10 11:13 JST にあなたのセッションが利用上限で止まったため、ユーザーの指示で Claude Code が開発を引き継いだ。やったことはこのファイルの「引き継ぎ後の対応」と git log（`feat(counterpoint)` 以降のコミット）にある。あなたのサブエージェント（trainer_web / counterpoint_engine / theory_review）が最後に何を送り合っていたかは暗号化されていて読めなかったので、未検証だった `local-tabs.spec.ts` と失敗していた Python テスト 3 件はコードとテストの意図から判断して直した。判断理由は下に書いた。納得できなければ差し戻してよい。

あなたが残していた検証用サーバー（127.0.0.1:8000 と :8017）は、ユーザーの了承を得て Claude Code が停止した。古いコードだったので、必要なら `sh scripts/start-counterpoint.sh` で立て直すこと。

## いま何が起きているか

- 2026-10-10 00:39〜11:13 JST、Codex が `/Users/arimura/Downloads/CODEX_HANDOFF_TAMANEGI_COUNTERPOINT.md` を仕様として対位法トレーナーを実装し、第1種の MVP を VPS に公開した。
- その後ユーザーが「第2種以降と履歴の端末間同期」「課題の最初に簡単なルール説明」を依頼。Codex はこれを実装し、公開直前に「複数タブで未同期の履歴が消える」問題を見つけて修正中に **利用上限で停止**。
- Codex のセッションログ: `~/.codex/sessions/2026/10/10/rollout-2026-10-10T00-39-19-*.jsonl`（親）と `00-40-20 / 00-40-37 / 00-40-45`（サブエージェント trainer_web / counterpoint_engine / theory_review）。サブエージェント間のメッセージは暗号化されていて読めない。

## 公開先と VPS

| 項目 | 値 |
| --- | --- |
| 公開 URL | https://tamanegi-sensei.intheblueshirt.com/counterpoint/ |
| 旧別名 | https://49-212-203-123.sslip.io/counterpoint/ |
| SSH | `ssh sakura`（ubuntu@49.212.203.123、さくら VPS） |
| トレーナー | `tamanegi-counterpoint.service` → 127.0.0.1:8766、`/home/ubuntu/projects/tamanegi-counterpoint/current` |
| 従来アプリ | `composition-advisor-server.service` → 127.0.0.1:8765（MIDI 添削。触らない） |
| Caddy | `/etc/caddy/Caddyfile`。`/counterpoint/*` を 8766 へ、それ以外を 8765 へ |
| 認証 | 既存の Basic 認証（`/etc/composition-advisor-server/env`）。資格情報はリポジトリに置かない |
| 履歴 DB | `/var/lib/tamanegi-counterpoint/history.sqlite3`（SQLite WAL、リリース切替で消えない） |

詳細な配置・戻し方は [docs/deployment.md](docs/deployment.md)。

**本番に載っているのは第1種のみのリリース `releases/20261010T0115`。** 第2〜5種・履歴同期・課題冒頭の説明はまだローカルにしかない。

## git の状態

トレーナー関連は **一度もコミットされていない**。`main` の HEAD は `e6f3754`（4月の MIDI 添削の変更）。

未コミット:

- 変更: `.gitignore` `README.md` `composition_advisor/README.md` `composition_advisor/pyproject.toml` `composition_advisor/uv.lock`
- 新規: `composition_advisor/composition_advisor/{api.py,history.py,counterpoint/}`、`composition_advisor/tests/test_{counterpoint,counterpoint_api,counterpoint_species,history}.py`、`web/`、`docs/`、`scripts/`、`deploy/`、この `HANDOFF.md`

Dropbox 上にあるので消えはしないが、コミットして push するまで履歴が残らない。

## Codex 停止時点（11:13 JST）に残っていた問題と、引き継ぎ後の対応

Codex 停止時点: `tsc` / `build` / unit 23 件は成功。`pytest` は 281 成功 / 3 失敗。複数タブ対策 (`App.tsx` + `local-tabs.spec.ts`) は編集途中で未検証。

Claude Code で対応済み（すべてローカル、未コミット）:

1. `grading_species.py`: 定旋律 1 小節のフラグメントで終止判定が `cf[-2]` を触って IndexError になるのをガード（`len(cf) >= 2`）。
2. `test_counterpoint_species.py` の例を 2 件修正。`test_metric_check_...` の旧例 (CF C4 D4 / CP E4 G4 A4) は G4→A4 が P5→P5 の並行5度で `direct_step_perfect` が原理的に出ない → CF C4 E4 / CP E4 A4 B4 に変更。`test_separate_bad_beats_...` の旧例の第4拍 C5–D5–C5 は仕様どおり許容される刺繍音 → 第3拍を A4 にして跳躍で入る不協和に変更。ルール自体は変えていない。
3. `App.tsx` の複数タブ対策を完成。原因: 他タブの提出を storage イベントで受け取ると `[store]` effect が自タブの下書きごと localStorage へ書き戻し、他タブの下書きを上書きしていた。対策: `change()`（自タブの操作）経由の変更だけが下書きを書き、他タブ・サーバー由来の履歴は保存済みスナップショットに「追加」するだけにした（`localEdits` / `persistedEdits` の ref）。マウント時は読んだ内容を 1 回だけ書く。
4. `docs/counterpoint.md` の検証手順と実行結果を更新。

現在のテスト状態: `pytest` 284 件成功、unit 23 件成功、e2e は標準サーバーで 13 件成功（同期テスト 1 件は自動 skip）、認証+履歴DB サーバーで `history-sync` と `local-tabs` の 2 件成功。**同期サーバーで全件は回さない**（`trainer.spec.ts` が履歴ゼロ前提で、蓄積履歴を数えて 3 件落ちる）。

## 残作業（優先順）

1. コミット（第1種 MVP / 第2〜5種 / 履歴同期 / デプロイ資料 のように分けるとよい）。
2. VPS へ配置: `cd web && VITE_BASE_PATH=/counterpoint/ npm run build` → 新リリースディレクトリへコピー → `uv sync --frozen --extra web --no-dev` → `current` を切替 → `systemctl restart tamanegi-counterpoint`。Caddy と従来アプリには触らない。手順は [docs/deployment.md](docs/deployment.md)。配置後は `web/dist` を `/` 用に再ビルドして戻す。
3. 配置後の確認: `/counterpoint/api/health` が 200、ログインして第2〜5種が選べる、別端末で履歴が同期される。`docs/deployment.md` に公開記録を追記。

## ローカルで動かす

```bash
# Python（uv が PATH にない場合は .venv-counterpoint を直接使う）
cd composition_advisor && ../.venv-counterpoint/bin/python -m pytest -q
# Web
cd web && npx tsc --noEmit && npx vitest run src && npm run build
# サーバー起動（ビルド済み dist を配信）
sh scripts/start-counterpoint.sh --port 8021
# e2e（別ターミナル、Chrome が必要）
cd web && COUNTERPOINT_BASE_URL=http://127.0.0.1:8021 npm run test:e2e
```

Codex が残した検証用サーバーがまだ動いているかもしれない（11:13 時点で 127.0.0.1:8000 と :8017 に python プロセス）。古いコードなので使わず、止めてよい。8000 が塞がっていると `start-counterpoint.sh` が既定ポートで起動できない。

## コードの要点

- 採点: `counterpoint/grading.py`（第1種・プロファイル v1）と `counterpoint/grading_species.py`（第2〜5種・v2）。第1種の v1 判定と過去履歴は互換維持が方針。
- 課題: `counterpoint/exercises.py`。`noteSlots` がリズムを固定し、小節を跨ぐ保持音は 1 つの長い Note。検証用解答 `_REFERENCE_ANSWERS` は API に出さない。
- 履歴: サーバー `history.py`（ログイン名ごと、append-only、ID 重複は内容一致なら無視、不一致なら 409）、クライアント `web/src/sync.ts` + `useHistorySync.ts`。未提出の回答はサーバーに送らない。
- 複数タブ: `App.tsx` の `useEffect`（保存前に localStorage の履歴をマージ）と `storage` イベントの受信処理。
- 仕様の原本: `~/Downloads/CODEX_HANDOFF_TAMANEGI_COUNTERPOINT.md`（646 行）。今回の範囲は 2 声・長調・固定リズム。

## 未実装・未検証（Codex の報告より）

Safari/Firefox、実機スピーカーでの聴感、五線譜からの直接入力、第5種の自由リズム、MIDI/MusicXML 入出力、短調・旋法、試験/コーチモード。
