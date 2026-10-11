# VPSへの公開

## 公開先と既存構成

- サイト: https://tamanegi-sensei.intheblueshirt.com/
- 対位法トレーナー: https://tamanegi-sensei.intheblueshirt.com/counterpoint/
- 従来の別名: https://49-212-203-123.sslip.io/
- SSH: `ssh sakura`（ubuntu@49.212.203.123）
- Caddy: `/etc/caddy/Caddyfile`。HTTPS終端とパスごとの振り分け。
- 従来アプリ: `composition-advisor-server.service`、`127.0.0.1:8765`、`/home/ubuntu/projects/composition-advisor-server`。
- トレーナー: `tamanegi-counterpoint.service`、`127.0.0.1:8766`、`/home/ubuntu/projects/tamanegi-counterpoint/current`。

過去の記録はローカルの `.claude/settings.local.json` と、隣接する `composition-advisor-server/README.md` にありました。現在のホスト名はVPS上のCaddy設定から確認しました。

## 配置方法

1. ローカルでPythonテストとフロントエンドのテストを実行。
2. `cd web && VITE_BASE_PATH=/counterpoint/ npm run build` で公開用の画面をビルド。
3. `composition_advisor/` のPythonソース・`pyproject.toml`・`uv.lock`、`web/dist/`、`deploy/sakura/` を、新しいリリースディレクトリへコピー。`.git`・仮想環境・個人資料・秘密情報は含めない。
4. VPS上のリリース内 `composition_advisor/` で `/home/ubuntu/.local/bin/uv sync --frozen --extra web --no-dev` を実行。
5. `current` を新しいリリースへ向け、[systemd設定](../deploy/sakura/tamanegi-counterpoint.service)でトレーナーだけを再起動。リポジトリのユニットファイルが VPS の `/etc/systemd/system/tamanegi-counterpoint.service` と異なる場合は、元ファイルをリリース内 `backups/` に保存してから置き換え、`systemctl daemon-reload` してから再起動する。
6. Caddyの既存ホスト内に [パス振り分け](../deploy/sakura/caddy-routes.txt) を追加。`/counterpoint/` を除く従来のURLは8765へ転送し、300秒のタイムアウトも維持する。`caddy validate` 成功後にreload。
7. 初回のみ、従来サーバーに [入口リンクのパッチ](../deploy/sakura/legacy-trainer-link.patch) を適用して再起動。事前に元ファイルをバックアップし、`patch --dry-run` とPython構文チェックを行う。

初回の設定変更前に、Caddyfileと従来サーバーの `app.py` をリリース配下の `backups/` に保存します。次回以降の通常更新では従来サーバーに触れません。

## 認証・確認

トレーナーは既存の `/etc/composition-advisor-server/env` にある `COMPOSITION_ADVISOR_USER` / `COMPOSITION_ADVISOR_PASSWORD` を利用します。認証情報はリポジトリに保存しません。両方が未設定ならローカル向けの認証なし動作、一方だけ・空文字なら起動時エラーになります。

- 公開ヘルスチェック: `/counterpoint/api/health`（認証不要）。
- 画面・採点API・静的ファイルは既存と同じBasic認証で保護。
- `systemctl status tamanegi-counterpoint`、`journalctl -u tamanegi-counterpoint` で稼働確認。
- 既存の `/healthz`、ログイン後のMIDI分析画面も確認。
- ブラウザテスト: `COUNTERPOINT_BASE_URL=https://tamanegi-sensei.intheblueshirt.com/counterpoint/ npm run test:e2e -- --trace off`。Basic認証は `COUNTERPOINT_AUTH_USER` / `COUNTERPOINT_AUTH_PASSWORD` に安全に渡す。秘密をコマンド引数やログへ書かない。

提出履歴と編集中の譜面はブラウザのlocalStorageにも保存します。提出履歴は同じBasic認証ユーザーでサーバーへ同期し、独自ドメインとsslip.io別名からも同じ履歴を取得できます。未提出の譜面・退避した回答は端末/オリジンごとに保持します。

履歴DBは `COUNTERPOINT_HISTORY_DB=/var/lib/tamanegi-counterpoint/history.sqlite3`。systemdの `StateDirectory=tamanegi-counterpoint` がubuntu所有・0700で作成し、リリース切替や再起動で失われません。サービスは `UMask=0077`、SQLiteはWALモードです。ユーザー名をキーに履歴を分離するため、認証ユーザー名を変更する際は履歴の移行も必要です。パスワード変更だけなら影響しません。

バックアップは稼働中のDB単体コピーではなくSQLiteのbackup APIを使います。例（秘密情報は不要）:

```bash
sudo -u ubuntu python3 - <<'PY'
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
root = Path('/var/lib/tamanegi-counterpoint')
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
with sqlite3.connect(root / 'history.sqlite3') as source:
    with sqlite3.connect(root / f'history-backup-{stamp}.sqlite3') as target:
        source.backup(target)
PY
```

この保存ディレクトリは非公開です。サーバー外への定期バックアップは別途設定してください。アプリを旧リリースへ戻してもDBは消さずに残します。

## 戻し方

トレーナーだけの更新は `current` を前リリースへ戻して `sudo systemctl restart tamanegi-counterpoint`。初回追加を取り消す場合は、バックアップしたCaddyfileを戻してvalidate/reload、バックアップした従来アプリを戻してそのサービスを再起動し、トレーナーを停止します。他のVPSサービスには触れません。

ローカルで使う画面に戻す場合は `cd web && npm run build` として、通常どおり `sh scripts/start-counterpoint.sh` で起動します。

## 2026-10-10 公開記録

- 配置リリース: `/home/ubuntu/projects/tamanegi-counterpoint/releases/20261010T0115`。
- 配置アーカイブSHA-256: `2a455553f8112e14070adfe3a9422982c2b8abc53f7cea221ad23a2f7784516c`。
- バックアップ: 同リリースの `backups/Caddyfile` と `backups/legacy-app.py`。
- Caddy設定検証成功、新サービスの自動起動を有効化。独自ドメインとsslip.io別名の両方でトレーナーのhealthが200、旧新画面は未認証401。従来の `/healthz` も200。
- Python 183件、フロントエンド単体12件、Basic認証付きサブパスを再現したChrome E2E 5件が成功。
- 公開サイトはChromeの既存ログインを使用して確認。8小節の入力、五線譜同期、再生開始と採点時の停止、適合判定、音高修正による結果の失効、再提出時の違反表示、再読み込み後の譜面・履歴保存が動作。従来画面のリンクと対位法レッスンの規則・プリセット表示も確認。
- ブラウザには確認用の提出2件が残っています。編集中の回答は「空の回答で新しい試行」に戻しました。
- 本番認証情報を取得する操作は自動審査で拒否されたため未実行。資格情報を抽出せず、Chromeが保持していたログインで公開版を検証しました。
- 未検証: Safari/Firefox、実機スピーカーでの聴感、今回変更していない従来のClaude APIによる添削。新トレーナーの第2種以降と端末間履歴同期は未実装。
- ローカル `web/dist` は通常の `/` 用へ再ビルド済み。未コミットのソースは保持し、Gitのcommit/pushは行っていません。

## 2026-10-11 公開記録（第2〜5種・履歴同期）

- 配置リリース: `/home/ubuntu/projects/tamanegi-counterpoint/releases/20261011T1225`。前リリースは `20261010T0115`（戻す場合は `current` をこちらへ向けて再起動）。
- 配置アーカイブSHA-256: `255107a75b79378a6a6105a66f7c418e19cc8a252cebbd2a3a9bb7adf77082a6`。内容は `composition_advisor/`（Pythonソース・pyproject・uv.lock）、`web/dist/`（`VITE_BASE_PATH=/counterpoint/`）、`deploy/sakura/`。
- systemd ユニットを更新: `COUNTERPOINT_HISTORY_DB`、`StateDirectory=tamanegi-counterpoint`、`UMask=0077` を追加。置換前のユニットは同リリースの `backups/tamanegi-counterpoint.service.before`。Caddy と従来アプリは変更なし。
- 確認: ローカル `/api/health` 200、`systemctl is-active` active、`/api/history/status` が `enabled: true`、`/api/exercises` に第1〜5種の7課題、画面が新しいアセット（`index-CF_R1DlT.js`）を配信。公開 URL とsslip.io別名で `/counterpoint/api/health` 200、画面は未認証401、従来の `/healthz` 200。履歴DB `/var/lib/tamanegi-counterpoint/history.sqlite3` が 0700 ディレクトリ・0600 で作成された。
- 認証付きの確認は VPS 上で `/etc/composition-advisor-server/env` を読み込んだシェルから実行し、資格情報は出力・転送していない。
- 配置元のコミット: `49b62e9`（docs）までの `main`。ローカル `web/dist` は `/` 用へ再ビルド済み。
- 未検証: ブラウザでログインしての第2〜5種の操作、別端末からの履歴同期（ローカルの e2e では確認済み）。
