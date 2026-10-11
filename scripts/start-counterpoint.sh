#!/bin/sh
# Start the built local trainer, using the isolated environment if available.
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ ! -f "$PROJECT_ROOT/web/dist/index.html" ]; then
    printf '%s\n' '先に web で npm ci && npm run build を実行してください。' >&2
    exit 1
fi
if [ -x "$PROJECT_ROOT/.venv-counterpoint/bin/python" ]; then
    exec "$PROJECT_ROOT/.venv-counterpoint/bin/python" -m composition_advisor.api "$@"
fi
cd "$PROJECT_ROOT/composition_advisor"
if command -v uv >/dev/null 2>&1; then
    exec uv run --extra web --frozen counterpoint "$@"
fi
printf '%s\n' 'uv が見つかりません。README のセットアップ手順を実行してください。' >&2
exit 1
