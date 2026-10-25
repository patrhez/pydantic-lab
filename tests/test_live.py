"""Opt-in real-provider verification; never part of the default paid path."""

import os
from pathlib import Path

import pytest

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.config import Settings
from pydantic_lab.sandbox.manager import SandboxManager


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="Set RUN_LIVE=1 for paid DeepSeek requests"
)
async def test_live_deepseek_reads_workspace_through_native_tools(store, local, tmp_path):
    (Path(local.repository) / "hello.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )
    settings = Settings.load()
    assert settings.api_key, "Configure a literal DEEPSEEK_API_KEY or environment variable"
    settings.state_dir = tmp_path
    settings.demo = False
    settings.request_limit = 6
    controls = Controls(store)
    rid = controls.send(
        local.id,
        "Use read_file to read /workspace/hello.py and state the function name. Do not edit files or run shell commands.",
        "queue",
        "live",
    )["run_id"]
    manager = SandboxManager(store)
    try:
        await Runner(settings, store, manager, detach_on_approval=True).execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert "greet" in run.answer.lower()
        assert any(r.tool == "read_file" and r.status == "succeeded" for r in run.receipts.values())
        print(f"Live provider passed: {settings.model}; {len(run.native_ids)} framework segments")
    finally:
        await manager.destroy(local.id)


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="Set RUN_LIVE=1 for paid DeepSeek requests"
)
async def test_live_deepseek_deferred_edit_approval(store, local, tmp_path):
    settings = Settings.load()
    assert settings.api_key
    settings.state_dir = tmp_path
    settings.demo = False
    settings.request_limit = 6
    controls = Controls(store)
    rid = controls.send(
        local.id,
        'Use write_file to create /workspace/note.txt containing exactly "native approval works". Do not run shell commands. Wait for tool approval, then report the result.',
        "queue",
        "live-edit",
    )["run_id"]
    manager = SandboxManager(store)
    runner = Runner(settings, store, manager, detach_on_approval=True)
    try:
        await runner.execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "awaiting_approval", run.error
        approval = next(a for a in run.approvals if a.status == "pending")
        assert approval.tool == "write_file" and approval.arguments["path"].endswith("note.txt")
        assert not (Path(local.repository) / "note.txt").exists()
        controls.decide(local.id, approval.id, True, "live-allow")
        await runner.execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert (Path(local.repository) / "note.txt").read_text().strip() == "native approval works"
        assert run.receipts[approval.call_id].status == "succeeded"
        print(
            f"Live deferred approval passed: {settings.model}; {len(run.native_ids)} framework segments"
        )
    finally:
        await manager.destroy(local.id)
