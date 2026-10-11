"""Local HTTP adapter for the counterpoint trainer; legacy CLI stays independent."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import secrets
from pathlib import Path
from typing import Any


def create_app(web_dist: Path | None = None, history_db: Path | None = None) -> Any:
    """Build the optional web app, serving a compiled UI when available.

    Args:
        web_dist: Override the frontend build folder (also useful in tests).
    """
    from fastapi import Body, FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.security import HTTPBasic
    from fastapi.staticfiles import StaticFiles

    from .counterpoint import get_exercise, grade, list_exercises, profile
    from .history import HistoryConflict, HistoryDatabase, SyncRequest
    from pydantic import ValidationError

    app = FastAPI(title="Tamanegi Counterpoint", version="2.0.0")

    username = os.environ.get("COMPOSITION_ADVISOR_USER")
    password = os.environ.get("COMPOSITION_ADVISOR_PASSWORD")
    if username is not None or password is not None:
        if not username or not password:
            raise RuntimeError(
                "COMPOSITION_ADVISOR_USER and COMPOSITION_ADVISOR_PASSWORD "
                "must both be nonempty when authentication is configured."
            )
        expected_user, expected_password = username.encode("utf-8"), password.encode("utf-8")
        basic = HTTPBasic(auto_error=False)

        @app.middleware("http")
        async def require_auth(request: Request, call_next: Any) -> Any:
            """Protect the static UI and every API except the GET health probe."""
            route_path = request.scope["path"]
            root_path = request.scope.get("root_path", "").rstrip("/")
            if root_path and (route_path == root_path or route_path.startswith(root_path + "/")):
                route_path = route_path[len(root_path):]
            if request.method == "GET" and route_path == "/api/health":
                return await call_next(request)
            try:
                credentials = await basic(request)
                if credentials:
                    # HTTPBasic's decoder is permissive about invalid base64
                    # characters; require a well-formed credential token too.
                    token = request.headers["Authorization"].partition(" ")[2]
                    base64.b64decode(token, validate=True)
            except (HTTPException, ValueError, binascii.Error):
                credentials = None
            valid_user = secrets.compare_digest(
                credentials.username.encode("utf-8") if credentials else b"", expected_user
            )
            valid_password = secrets.compare_digest(
                credentials.password.encode("utf-8") if credentials else b"", expected_password
            )
            if not (valid_user and valid_password):
                return JSONResponse(
                    {"detail": "認証が必要です。"}, status_code=401,
                    headers={"WWW-Authenticate": "Basic"},
                )
            return await call_next(request)

    db_path = history_db or os.environ.get("COUNTERPOINT_HISTORY_DB")
    history = HistoryDatabase(Path(db_path)) if db_path and username and password else None

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Report local service availability without consulting an LLM."""
        return {"status": "ok"}

    @app.get("/api/exercises")
    def exercises() -> list[dict[str, Any]]:
        """Return public exercise metadata, excluding verification answers."""
        return list_exercises()

    @app.get("/api/exercises/{exercise_id}")
    def exercise(exercise_id: str) -> dict[str, Any]:
        """Look up one immutable exercise."""
        try:
            return get_exercise(exercise_id)
        except KeyError as exc:
            raise HTTPException(404, "課題が見つかりません。") from exc

    @app.get("/api/profile")
    def rule_profile(version: str | None = None) -> dict[str, Any]:
        """Describe the actual versioned rule profile used for assessment."""
        try:
            return profile(version)
        except KeyError as exc:
            raise HTTPException(404, "規則のバージョンが見つかりません。") from exc

    @app.post("/api/grade")
    def assessment(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Grade a snapshot deterministically using only server-owned rules."""
        try:
            return grade(payload)
        except KeyError as exc:
            raise HTTPException(404, "課題が見つかりません。") from exc

    @app.get("/api/history/status")
    def history_status() -> dict[str, Any]:
        """Sync is available only with authenticated, durable storage."""
        return {"enabled": history is not None,
                "message": "同じログインの端末で提出履歴を同期します。" if history else
                "この環境では履歴はブラウザ内に保存されます。"}

    @app.post("/api/history/sync")
    def history_sync(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Merge immutable submissions, then return a revision-ordered page."""
        if history is None:
            raise HTTPException(503, "履歴同期はこの環境で設定されていません。")
        try:
            request = SyncRequest.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(422, "履歴の形式を確認してください。端末の履歴は保持されています。") from exc
        try:
            return history.sync(username, request)
        except HistoryConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    # Keep API errors JSON even when the static frontend is mounted at /.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(path: str) -> None:
        """Reject unknown API paths."""
        raise HTTPException(404, "APIが見つかりません。")

    default_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    dist = web_dist or Path(os.environ.get("COUNTERPOINT_WEB_DIST", default_dist))
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="trainer")
    else:
        @app.get("/", response_class=HTMLResponse)
        def build_help() -> str:
            """Explain how to build the UI if only Python has been installed."""
            return (
                '<html lang="ja"><meta charset="utf-8"><title>対位法トレーナー</title>'
                '<h1>画面のビルドが必要です</h1>'
                '<p>リポジトリの web ディレクトリで <code>npm ci &amp;&amp; npm run build</code>'
                ' を実行し、このサーバーを再起動してください。</p>'
                '<p>開発時は <code>npm run dev</code> でポート5173から利用できます。</p></html>'
            )
    return app


def main() -> None:
    """Start the trainer on loopback; network exposure must be explicitly chosen."""
    parser = argparse.ArgumentParser(description="対位法トレーナー（ローカル）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        import uvicorn
        app = create_app()
    except ImportError as exc:
        raise SystemExit("Web依存が必要です: uv sync --extra web") from exc
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
