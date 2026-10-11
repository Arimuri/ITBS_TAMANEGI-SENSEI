"""Real SQLite + HTTP checks for retries, device merges and durable isolation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from composition_advisor.api import create_app
from composition_advisor.counterpoint import grade
from composition_advisor.counterpoint.exercises import reference_submission
from composition_advisor.history import HistoryConflict, HistoryDatabase, SyncRequest


def record():
    submission = reference_submission("species1-c-above")
    return {"id": str(uuid4()), "attemptId": str(uuid4()), "submittedAt": "2026-10-10T01:00:00.000Z",
            "notes": submission["notes"], "result": grade(submission), "hints": {}}


def request(records=(), after=0):
    return SyncRequest.model_validate({"records": list(records), "after": after})


def test_retry_restart_and_account_isolation(tmp_path):
    path = tmp_path / "state" / "history.sqlite3"
    db = HistoryDatabase(path)
    item = record()
    first = db.sync("alice", request([item]))
    assert first["records"] == [item]
    assert db.sync("alice", request([item])) == first
    restored = HistoryDatabase(path)
    assert restored.sync("alice", request())["records"] == [item]
    assert restored.sync("bob", request())["records"] == []
    assert restored.sync("alice", request(after=first["cursor"]))["records"] == []


def test_parallel_devices_union_and_monotonic_hints(tmp_path):
    db = HistoryDatabase(tmp_path / "history.sqlite3")
    item = record()
    db.sync("alice", request([item]))
    left, right = deepcopy(item), deepcopy(item)
    left["hints"] = {"rule-1": 2}
    right["hints"] = {"rule-1": 1, "rule-2": 1}
    others = [record() for _ in range(8)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda r: db.sync("alice", request([r])), [left, right, *others]))
    result = db.sync("alice", request())
    assert len(result["records"]) == 9
    assert next(r for r in result["records"] if r["id"] == item["id"])["hints"] == {"rule-1": 2, "rule-2": 1}
    db.sync("alice", request([item]))
    assert len(db.sync("alice", request())["records"]) == 9


def test_conflicting_uuid_never_overwrites_and_batch_rolls_back(tmp_path):
    db = HistoryDatabase(tmp_path / "history.sqlite3")
    item = record()
    db.sync("alice", request([item]))
    changed = deepcopy(item)
    changed["notes"][0]["pitch"]["octave"] = 4
    with pytest.raises(HistoryConflict):
        db.sync("alice", request([record(), changed]))
    assert db.sync("alice", request())["records"] == [item]


def test_pagination_preserves_every_record(tmp_path):
    db = HistoryDatabase(tmp_path / "history.sqlite3")
    items = [record() for _ in range(205)]
    for start in range(0, len(items), 100):
        db.sync("alice", request(items[start:start + 100]))
    first = db.sync("alice", request())
    assert first["hasMore"] and len(first["records"]) == 200
    second = db.sync("alice", request(after=first["cursor"]))
    assert not second["hasMore"] and len(second["records"]) == 5
    assert {r["id"] for r in first["records"] + second["records"]} == {r["id"] for r in items}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPOSITION_ADVISOR_USER", "learner")
    monkeypatch.setenv("COMPOSITION_ADVISOR_PASSWORD", "test-only")
    client = TestClient(create_app(tmp_path, tmp_path / "history.sqlite3"))
    client.auth = ("learner", "test-only")
    return client


def test_authenticated_api_sync_is_idempotent(client):
    assert client.get("/api/history/status").json()["enabled"]
    assert client.get("/api/history/status", auth=("wrong", "wrong")).status_code == 401
    item = record()
    for _ in range(2):
        response = client.post("/api/history/sync", json={"records": [item]})
        assert response.status_code == 200 and response.json()["records"] == [item]
    changed = deepcopy(item)
    changed["attemptId"] = "conflict"
    assert client.post("/api/history/sync", json={"records": [changed]}).status_code == 409
    assert client.post("/api/history/sync", json={}).json()["records"] == [item]


def test_sync_under_reverse_proxy_prefix_and_profile_compatibility(client):
    prefixed = TestClient(client.app, root_path="/counterpoint")
    assert prefixed.get("/counterpoint/api/history/status").status_code == 401
    assert prefixed.post("/counterpoint/api/history/sync", json={}).status_code == 401
    prefixed.auth = ("learner", "test-only")
    item = record()
    response = prefixed.post("/counterpoint/api/history/sync", json={"records": [item]})
    assert response.status_code == 200 and response.json()["records"] == [item]
    assert prefixed.get("/counterpoint/api/profile?version=1").json()["version"] == "1"
    assert prefixed.get("/counterpoint/api/profile?version=2").json()["version"] == "2"
    assert prefixed.get("/counterpoint/api/profile?version=missing").status_code == 404


@pytest.mark.parametrize("change", [
    lambda r: r.update(submittedAt="invalid"),
    lambda r: r.update(submittedAt="2026-10-10T00:00:00"),
    lambda r: r.update(hints={"x": -1}),
    lambda r: r.update(hints={"x": True}),
    lambda r: r["notes"][0].update(voiceId="cf"),
    lambda r: r.update(extra="unexpected"),
])
def test_invalid_history_is_rejected_without_deleting_saved_data(client, change):
    item = record()
    client.post("/api/history/sync", json={"records": [item]})
    bad = record()
    change(bad)
    assert client.post("/api/history/sync", json={"records": [bad]}).status_code == 422
    assert client.post("/api/history/sync", json={}).json()["records"] == [item]


def test_oversized_batch_and_invalid_cursor(client):
    assert client.post("/api/history/sync", json={"records": [record()] * 101}).status_code == 422
    assert client.post("/api/history/sync", json={"after": -1}).status_code == 422


def test_no_unprotected_shared_history(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPOSITION_ADVISOR_USER", raising=False)
    monkeypatch.delenv("COMPOSITION_ADVISOR_PASSWORD", raising=False)
    client = TestClient(create_app(tmp_path, tmp_path / "history.sqlite3"))
    assert not client.get("/api/history/status").json()["enabled"]
    assert client.post("/api/history/sync", json={}).status_code == 503
    assert not (tmp_path / "history.sqlite3").exists()
