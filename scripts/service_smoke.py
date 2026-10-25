"""Exercise a disposable session against Compose. Requires LAB_DEMO_TOOL=write_file.

With --chaos, restart services and stop Redis during the test. Other sessions
must be idle. Only this script's session and workspace are deleted.
"""

import argparse
import json
import subprocess
import time
import uuid

import httpx


def compose(*args):
    result = subprocess.run(["docker", "compose", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Compose {' '.join(args[:3])} failed: {result.stderr[-500:]}")
    return result.stdout.strip()


def wait(get, predicate, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = get()
        if predicate(value):
            return value
        time.sleep(0.15)
    raise AssertionError(f"Timed out: {value.get('status')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chaos", action="store_true")
    args = parser.parse_args()
    agent_id = compose("ps", "-q", "agent")
    environment = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "--format", "{{json .Config.Env}}", agent_id], text=True
        )
    )
    assert "LAB_DEMO=1" in environment and "LAB_DEMO_TOOL=write_file" in environment, (
        "Start the agent with LAB_DEMO=1 LAB_DEMO_TOOL=write_file before this test"
    )
    sid = "smoke" + uuid.uuid4().hex[:20]
    client = httpx.Client(base_url="http://127.0.0.1:8000/api", timeout=60)

    def post(path, **body):
        response = client.post(path, json={"request_id": uuid.uuid4().hex, **body})
        assert response.is_success, response.text
        return response.json()

    def snapshot():
        deadline = time.monotonic() + 45
        while True:
            try:
                response = client.get(f"/sessions/{sid}")
                if response.status_code not in {502, 503}:
                    response.raise_for_status()
                    return response.json()["session"]
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise AssertionError("API did not become ready")
            time.sleep(0.25)

    try:
        post(
            "/sessions",
            repository="https://github.com/octocat/Hello-World.git",
            title="Disposable service smoke",
            request_id=sid,
        )
        wait(snapshot, lambda s: s["status"] == "ready")
        rid = post(f"/sessions/{sid}/messages", content="Write a file", mode="queue")["run_id"]
        current = wait(snapshot, lambda s: s["status"] == "awaiting_approval")
        approval = current["runs"][0]["approvals"][0]
        sandbox = current["sandbox"]["container"]
        preview = client.get(
            f"/sessions/{sid}/workspace/approval", params={"approval_id": approval["id"]}
        )
        assert preview.is_success and "+" in preview.json()["diff"], preview.text
        assert snapshot()["inspection"] == {}, "Derived diffs must not be persisted"
        if args.chaos:
            compose("up", "-d", "--build", "--no-deps", "api", "web")
            assert compose("ps", "-q", "agent") == agent_id
            assert snapshot()["sandbox"]["container"] == sandbox
            compose("restart", "agent")
            wait(snapshot, lambda s: s["status"] == "awaiting_approval")
            assert snapshot()["runs"][0]["approvals"][0]["status"] == "pending"
            compose("stop", "redis")
        post(f"/sessions/{sid}/approvals/{approval['id']}", allow=True)
        current = wait(snapshot, lambda s: s["runs"][0]["status"] == "completed")
        assert current["runs"][0]["receipts"][approval["call_id"]]["status"] == "succeeded"
        assert len(current["runs"][0]["native_ids"]) == 2
        diff = client.get(f"/sessions/{sid}/workspace/diff").json()
        assert diff["untracked"], diff
        assert snapshot()["inspection"] == {}
        with client.stream("GET", f"/sessions/{sid}/events?after=0") as response:
            ids = []
            for line in response.iter_lines():
                if line.startswith("id: "):
                    ids.append(int(line[4:]))
                    if len(ids) == 3:
                        break
        with client.stream("GET", f"/sessions/{sid}/events?after={ids[-1]}") as response:
            for line in response.iter_lines():
                if line.startswith("id: "):
                    assert int(line[4:]) > ids[-1]
                    break
        assert current["runs"][0]["id"] == rid
        print(
            "PASS: MySQL native continuation, pending approval restart, transient diffs, SSE replay"
        )
        if args.chaos:
            print(
                "PASS: API/Web rebuild leaves agent and sandbox intact; Redis loss preserves results"
            )
    finally:
        if args.chaos:
            compose("start", "redis")
        try:
            current = snapshot()
            if any(r["status"] in {"running", "awaiting_approval"} for r in current["runs"]):
                post(f"/sessions/{sid}/stop")
                wait(snapshot, lambda s: s["status"] == "stopped")
            post(f"/sessions/{sid}/actions", kind="delete", payload={"confirmation": "DELETE"})
            wait(snapshot, lambda s: s["status"] == "deleted")
        finally:
            client.close()


if __name__ == "__main__":
    main()
