# エージェント向けメモ

このリポジトリで作業を始める前に [HANDOFF.md](HANDOFF.md) を読むこと。直近のセッションで何が起き、何が本番に載っていて、何が残っているかを書いてある。作業を終えるときは HANDOFF.md を更新する。

- 対位法トレーナーの使い方・検証: [docs/counterpoint.md](docs/counterpoint.md)
- 採点方針と出典: [docs/counterpoint-theory.md](docs/counterpoint-theory.md)（第1種）、[docs/counterpoint-species.md](docs/counterpoint-species.md)（第2〜5種）
- VPS への配置・戻し方: [docs/deployment.md](docs/deployment.md)
- 既存の MIDI 添削 CLI: [composition_advisor/README.md](composition_advisor/README.md)。`critique/`・`llm/`・MIDI 入出力には対位法トレーナーの作業で手を入れない。

認証情報（VPS の Basic 認証など）はリポジトリに書かない。本番の履歴 DB は消さない。
