"""HTTP boundary and UI serving regression tests for the local trainer."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from composition_advisor.api import create_app


@pytest.fixture(autouse=True)
def isolated_auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never depend on a developer's real deployment credentials."""
    monkeypatch.delenv("COMPOSITION_ADVISOR_USER", raising=False)
    monkeypatch.delenv("COMPOSITION_ADVISOR_PASSWORD", raising=False)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create an API client without requiring frontend dependencies."""
    return TestClient(create_app(tmp_path))


def test_public_exercises_and_profile_exclude_answers(client: TestClient) -> None:
    exercises = client.get("/api/exercises").json()
    assert len(exercises) >= 3
    for exercise in exercises:
        assert 8 <= len(exercise["cantus"]) <= 12
        assert not ({"solution", "solutions", "answer", "answers"} & exercise.keys())
        assert client.get(f"/api/exercises/{exercise['id']}").json() == exercise
    assert client.get("/api/profile").json()["rules"]


def test_empty_submission_is_incomplete_not_a_pass(client: TestClient) -> None:
    exercise = client.get("/api/exercises").json()[0]
    payload = {
        "exerciseId": exercise["id"], "notes": [], "cantus": exercise["cantus"],
        "ruleProfileId": exercise["ruleProfileId"],
        "ruleProfileVersion": exercise["ruleProfileVersion"],
    }
    first = client.post("/api/grade", json=payload)
    assert first.status_code == 200
    assert first.json()["assessmentStatus"] == "incomplete"
    assert first.json()["passed"] is False
    assert first.json() == client.post("/api/grade", json=payload).json()


def test_invalid_http_requests_and_unknown_exercises(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/exercises/missing").status_code == 404
    assert client.post("/api/grade", json={"exerciseId": "missing"}).status_code == 404
    assert client.post("/api/grade", json=[]).status_code == 422
    assert client.post("/api/grade", content="broken", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.get("/api/missing").status_code == 404


def test_build_help_and_static_files(tmp_path: Path) -> None:
    assert "npm run build" in TestClient(create_app(tmp_path)).get("/").text
    (tmp_path / "index.html").write_text("<h1>Counterpoint</h1>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("/* local bundle */")
    built = TestClient(create_app(tmp_path))
    assert built.get("/").text == "<h1>Counterpoint</h1>"
    assert built.get("/assets/app.js").status_code == 200
    assert built.get("/api/health").json()["status"] == "ok"
    assert built.get("/api/not-found").headers["content-type"].startswith("application/json")


@pytest.fixture
def protected_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("COMPOSITION_ADVISOR_USER", "learner")
    monkeypatch.setenv("COMPOSITION_ADVISOR_PASSWORD", "test-only:password")
    (tmp_path / "index.html").write_text("<h1>Private trainer</h1>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("/* protected bundle */")
    return TestClient(create_app(tmp_path))


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/api/exercises", "/api/profile", "/docs", "/openapi.json", "/api/unknown"])
def test_auth_protects_static_and_all_application_routes(protected_client: TestClient, path: str) -> None:
    response = protected_client.get(path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Basic"
    assert "test-only" not in response.text and "learner" not in response.text


@pytest.mark.parametrize("credentials", [("learner", "wrong"), ("wrong", "test-only:password"), ("", ""), ("learner", "")])
def test_auth_rejects_wrong_user_or_password(protected_client: TestClient, credentials: tuple[str, str]) -> None:
    assert protected_client.get("/api/exercises", auth=credentials).status_code == 401


@pytest.mark.parametrize("header", [
    "Bearer arbitrary-token", "Basic", "Basic !!!", "Basic abc",
    "Basic " + base64.b64encode(b"no-colon").decode(),
    "Basic " + base64.b64encode(b"\xff:\xfe").decode(),
    "Basic " + base64.b64encode(b"learner:test-only:password").decode() + "!!!",
])
def test_malformed_credentials_are_unauthorized_not_server_errors(protected_client: TestClient, header: str) -> None:
    assert protected_client.get("/", headers={"Authorization": header}).status_code == 401


def test_valid_auth_serves_ui_assets_and_grade(protected_client: TestClient) -> None:
    auth = ("learner", "test-only:password")
    assert protected_client.get("/", auth=auth).text == "<h1>Private trainer</h1>"
    assert protected_client.get("/assets/app.js", auth=auth).status_code == 200
    exercises = protected_client.get("/api/exercises", auth=auth).json()
    ex = exercises[0]
    payload = {"exerciseId": ex["id"], "notes": [], "cantus": ex["cantus"],
               "ruleProfileId": ex["ruleProfileId"], "ruleProfileVersion": ex["ruleProfileVersion"]}
    assert protected_client.post("/api/grade", json=payload).status_code == 401
    response = protected_client.post("/api/grade", json=payload, auth=auth)
    assert response.status_code == 200 and response.json()["assessmentStatus"] == "incomplete"


def test_only_exact_get_health_probe_is_public(protected_client: TestClient) -> None:
    assert protected_client.get("/api/health").json() == {"status": "ok"}
    assert protected_client.get("/api/health?probe=1").status_code == 200
    assert protected_client.post("/api/health").status_code == 401
    assert protected_client.head("/api/health").status_code == 401
    assert protected_client.get("/api/health/", follow_redirects=False).status_code == 401


def test_auth_and_health_under_reverse_proxy_root_path(protected_client: TestClient) -> None:
    prefixed = TestClient(protected_client.app, root_path="/counterpoint")
    assert prefixed.get("/counterpoint/api/health").json() == {"status": "ok"}
    assert prefixed.post("/counterpoint/api/health").status_code == 401
    assert prefixed.get("/counterpoint-extra/api/health").status_code == 401
    for path in ["/counterpoint/", "/counterpoint/assets/app.js", "/counterpoint/api/exercises"]:
        assert prefixed.get(path).status_code == 401
        assert prefixed.get(path, auth=("learner", "test-only:password")).status_code == 200


@pytest.mark.parametrize("user,password", [("learner", None), (None, "password"), ("", "password"), ("learner", ""), ("", "")])
def test_partial_or_empty_auth_configuration_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, user: str | None, password: str | None) -> None:
    if user is not None:
        monkeypatch.setenv("COMPOSITION_ADVISOR_USER", user)
    if password is not None:
        monkeypatch.setenv("COMPOSITION_ADVISOR_PASSWORD", password)
    with pytest.raises(RuntimeError, match="must both be nonempty"):
        create_app(tmp_path)
