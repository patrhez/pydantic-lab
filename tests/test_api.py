from fastapi.testclient import TestClient

from pydantic_lab.api.server import create_app
from pydantic_lab.application.controls import Controls
from pydantic_lab.models import Approval, Session


def test_session_creation_validation_and_idempotency(store, settings):
    client = TestClient(create_app(settings, store))
    assert client.post("/api/sessions", json={"repository": "file:///etc"}).status_code == 409
    body = {"repository": "https://github.com/octocat/Hello-World.git", "request_id": "stable123"}
    a = client.post("/api/sessions", json=body)
    b = client.post("/api/sessions", json=body)
    assert a.status_code == b.status_code == 202
    assert a.json()["id"] == b.json()["id"]
    assert len(store.list()) == 1
    assert (
        client.post(
            "/api/sessions", json={**body, "branch": "main", "commit": "a" * 40}
        ).status_code
        == 409
    )


def test_api_keeps_history_internal_and_defers_filesystem_work(store, local, settings):
    client = TestClient(create_app(settings, store))
    response = client.get("/api/sessions/" + local.id)
    assert "history" not in response.json()["session"]
    request = client.post(
        "/api/sessions/" + local.id + "/actions", json={"kind": "start", "request_id": "start"}
    )
    assert request.status_code == 202
    assert store.get(local.id).actions[0]["status"] == "queued"
    assert "diff" not in store.get(local.id).inspection


def test_api_rejects_workspace_mutations_during_run(store, local, settings):
    controls = Controls(store)
    rid = controls.send(local.id, "Run", "queue", "start")["run_id"]
    store.mutate(local.id, lambda s, e: setattr(s.run(rid), "status", "running"))
    client = TestClient(create_app(settings, store))
    for kind in ("delete", "network", "rebuild", "trust"):
        assert (
            client.post(
                "/api/sessions/" + local.id + "/actions",
                json={"kind": kind, "payload": {"confirmation": "DELETE", "enabled": True}},
            ).status_code
            == 409
        )


def test_provisioning_approval_works_while_chat_is_disabled(store, settings):
    session = Session(
        title="Setup",
        mode="server",
        repository="https://github.com/octocat/Hello-World.git",
        status="provisioning",
    )
    approval = Approval(
        call_id="setup0",
        tool="run_command",
        arguments={"command": "uv sync"},
        digest="hash",
        policy_revision="1",
        setup=True,
    )
    session.setup_approvals.append(approval)
    store.create(session)
    client = TestClient(create_app(settings, store))
    assert (
        client.post(f"/api/sessions/{session.id}/messages", json={"content": "hello"}).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/sessions/{session.id}/approvals/{approval.id}", json={"allow": True}
        ).status_code
        == 200
    )
    assert store.get(session.id).setup_approvals[0].status == "allowed"
