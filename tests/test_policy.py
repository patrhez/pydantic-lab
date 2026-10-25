from pathlib import Path

import pytest

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.sandbox.manager import SandboxManager
from tests.helpers import one_tool


@pytest.mark.integration
async def test_auto_allow_still_records_receipts_without_approval(store, local, settings):
    store.mutate(local.id, lambda s, e: s.policy.auto_allow.append("write_file"))
    manager = SandboxManager(store)
    rid = Controls(store).send(local.id, "Write", "queue", "auto")["run_id"]
    try:
        await Runner(
            settings,
            store,
            manager,
            model=one_tool("write_file", {"path": "allowed.txt", "content": "allowed"}),
        ).execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert not run.approvals
        assert next(iter(run.receipts.values())).status == "succeeded"
        assert (Path(local.repository) / "allowed.txt").read_text() == "allowed"
    finally:
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_auto_allow_cannot_override_protected_path(store, local, settings):
    path = Path(local.repository) / ".env"
    path.write_text("unchanged")
    store.mutate(local.id, lambda s, e: s.policy.auto_allow.append("*"))
    manager = SandboxManager(store)
    rid = Controls(store).send(local.id, "Write", "queue", "denied")["run_id"]
    try:
        await Runner(
            settings,
            store,
            manager,
            model=one_tool("write_file", {"path": ".env", "content": "changed"}),
        ).execute(local.id, rid)
        assert path.read_text() == "unchanged"
        assert not store.get(local.id).run(rid).receipts
    finally:
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_command_failure_is_not_a_success_receipt(store, local, settings):
    store.mutate(local.id, lambda s, e: s.policy.auto_allow.append("run_command"))
    manager = SandboxManager(store)
    rid = Controls(store).send(local.id, "Execute", "queue", "failure")["run_id"]
    try:
        await Runner(
            settings,
            store,
            manager,
            model=one_tool("run_command", {"command": "python3 -c 'raise SystemExit(7)'"}),
        ).execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        receipt = next(iter(run.receipts.values()))
        assert receipt.status == "failed", receipt.result
        assert "7" in str(receipt.result)
    finally:
        await manager.destroy(local.id)
