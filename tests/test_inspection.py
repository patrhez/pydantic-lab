from pathlib import Path
from types import SimpleNamespace

import pytest

from pydantic_lab.application.inspection import inspect_workspace
from pydantic_lab.models import Approval, Run
from pydantic_lab.sandbox.manager import SandboxManager


@pytest.mark.integration
async def test_proposed_and_current_diff_are_transient_reads(store, local):
    path = Path(local.repository) / "sample.py"
    path.write_text("old\n")
    approval = Approval(
        call_id="edit",
        tool="edit_file",
        arguments={"path": "sample.py", "old_text": "old", "new_text": "new"},
        digest="identity",
        policy_revision="1",
    )
    run = Run(prompt="Edit", status="awaiting_approval", approvals=[approval])
    store.mutate(local.id, lambda s, e: s.runs.append(run))
    worker = SimpleNamespace(store=store, sandbox=SandboxManager(store))
    try:
        preview = await inspect_workspace(worker, local.id, "approval", approval.id)
        assert "-old" in preview["diff"] and "+new" in preview["diff"]
        assert path.read_text() == "old\n"
        assert store.get(local.id).inspection == {}
        assert not store.get(local.id).run(run.id).receipts
    finally:
        await worker.sandbox.destroy(local.id)
