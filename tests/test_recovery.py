import asyncio
import os
import sys
from pathlib import Path

import pytest

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.sandbox.manager import SandboxManager
from tests.helpers import one_tool
from tests.test_runtime import wait_for


async def child(store, settings, sid, rid, tool, arguments, pause=0):
    import json

    source = """
import asyncio,json,sys
from pathlib import Path
from pydantic_lab.config import Settings
from pydantic_lab.storage.control import ControlStore
from pydantic_lab.application.runner import Runner
from pydantic_lab.sandbox.manager import SandboxManager
from tests.helpers import one_tool
async def main():
    database,state,sid,rid,tool,arguments,pause=sys.argv[1:]
    store=ControlStore(database)
    settings=Settings(state_dir=Path(state),demo=True)
    await Runner(settings,store,SandboxManager(store),model=one_tool(tool,json.loads(arguments),pause_after_tool=float(pause))).execute(sid,rid)
asyncio.run(main())
"""
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        source,
        str(store.engine.url),
        str(settings.state_dir),
        sid,
        rid,
        tool,
        json.dumps(arguments),
        str(pause),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYDANTIC_AI_NO_BANNER": "1"},
    )


@pytest.mark.integration
async def test_sigkill_at_approval_restores_native_pending_call(store, local, settings):
    controls = Controls(store)
    rid = controls.send(local.id, "Write result", "queue", "first")["run_id"]
    arguments = {"path": "result.txt", "content": "written"}
    process = await child(store, settings, local.id, rid, "write_file", arguments)
    manager = SandboxManager(store)
    try:
        session = await wait_for(
            store, local.id, lambda s: s.run(rid).status == "awaiting_approval"
        )
        process.kill()
        await process.wait()
        approval = session.run(rid).approvals[0]
        controls.decide(local.id, approval.id, True, "allow")
        await Runner(settings, store, manager, model=one_tool("write_file", arguments)).execute(
            local.id, rid
        )
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert (Path(local.repository) / "result.txt").read_text() == "written"
        assert len([e for e in store.replay(local.id) if e["kind"] == "execution.started"]) == 1
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_sigkill_after_effect_pauses_and_manual_continue_never_reexecutes(
    store, local, settings
):
    workspace = Path(local.repository)
    (workspace / "slow.py").write_text(
        "from pathlib import Path\nimport time\np=Path('counter.txt')\np.write_text(str(int(p.read_text())+1) if p.exists() else '1')\ntime.sleep(3)\n"
    )
    store.mutate(local.id, lambda s, e: setattr(s.policy, "auto_allow", ["run_command"]))
    controls = Controls(store)
    rid = controls.send(local.id, "Run the script", "queue", "first")["run_id"]
    arguments = {"command": "python3 slow.py"}
    process = await child(store, settings, local.id, rid, "run_command", arguments)
    manager = SandboxManager(store)
    try:
        async with asyncio.timeout(30):
            while not (workspace / "counter.txt").exists():
                if process.returncode is not None:
                    raise AssertionError((await process.stderr.read()).decode())
                await asyncio.sleep(0.05)
        process.kill()
        await process.wait()
        runner = Runner(settings, store, manager, model=one_tool("run_command", arguments))
        await runner.execute(local.id, rid)
        assert store.get(local.id).run(rid).status == "outcome_unknown"
        assert (workspace / "counter.txt").read_text() == "1"
        controls.recover(local.id, "continue", True, "inspect")
        await runner.execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert (workspace / "counter.txt").read_text() == "1"
        assert run.receipts["operation-1"].status == "reconciled"
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_changed_file_after_approval_is_not_overwritten(store, local, settings):
    path = Path(local.repository) / "result.txt"
    path.write_text("original")
    controls = Controls(store)
    rid = controls.send(local.id, "Edit result", "queue", "first")["run_id"]
    manager = SandboxManager(store)
    arguments = {"path": "result.txt", "content": "agent edit"}
    try:
        runner = Runner(
            settings,
            store,
            manager,
            model=one_tool("write_file", arguments),
            detach_on_approval=True,
        )
        await runner.execute(local.id, rid)
        approval = store.get(local.id).run(rid).approvals[0]
        path.write_text("concurrent user edit")
        controls.decide(local.id, approval.id, True, "allow")
        await runner.execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert path.read_text() == "concurrent user edit"
        assert not run.receipts
    finally:
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_sigkill_after_settled_tool_result_does_not_repeat_effect(store, local, settings):
    store.mutate(local.id, lambda s, e: s.policy.auto_allow.append("run_command"))
    path = Path(local.repository) / "counter.txt"
    (Path(local.repository) / "increment.py").write_text(
        "from pathlib import Path\np = Path('counter.txt')\np.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n"
    )
    arguments = {"command": "python3 increment.py"}
    rid = Controls(store).send(local.id, "Increment once", "queue", "settled")["run_id"]
    process = await child(store, settings, local.id, rid, "run_command", arguments, pause=60)
    manager = SandboxManager(store)
    try:
        await wait_for(
            store,
            local.id,
            lambda s: (
                s.run(rid).request_count >= 2
                and any(r.status == "succeeded" for r in s.run(rid).receipts.values())
            ),
        )
        process.kill()
        await process.wait()
        await Runner(settings, store, manager, model=one_tool("run_command", arguments)).execute(
            local.id, rid
        )
        assert store.get(local.id).run(rid).status == "completed"
        assert path.read_text() == "1"
        assert len([e for e in store.replay(local.id) if e["kind"] == "execution.started"]) == 1
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await manager.destroy(local.id)
