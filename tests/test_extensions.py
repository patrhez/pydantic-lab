import asyncio
import json
import socket
import sys
from pathlib import Path

import httpx
import pytest

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.runtime.extensions import discover
from pydantic_lab.sandbox.manager import SandboxManager
from tests.helpers import one_tool


@pytest.mark.integration
async def test_stdio_mcp_runs_inside_sandbox_and_requires_trust(store, local, settings):
    workspace = Path(local.repository)
    (workspace / "examples").mkdir()
    (workspace / "examples/mcp_server.py").write_text(Path("examples/mcp_server.py").read_text())
    (workspace / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "example": {"command": "python3", "args": ["/workspace/examples/mcp_server.py"]}
                }
            }
        )
    )
    store.mutate(local.id, lambda s, e: setattr(s.sandbox, "image", "pydantic-lab-agent:latest"))
    manager = SandboxManager(store)
    try:
        backend = await manager.ensure(local.id)
        found = await discover(backend)
        assert "mcp" in found
        assert not store.get(local.id).trust
        store.mutate(
            local.id,
            lambda s, e: (
                s.trust.update({"mcp": found["mcp"]["identity"]}),
                setattr(s.policy, "auto_allow", ["example_*"]),
            ),
        )
        rid = Controls(store).send(local.id, "Add two numbers", "queue", "first")["run_id"]
        runner = Runner(settings, store, manager, model=one_tool("example_add", {"a": 2, "b": 3}))
        await runner.execute(local.id, rid)
        result = store.get(local.id).run(rid)
        assert result.status == "completed", result.error
        assert "5" in str(result.receipts["operation-1"].result)
        old = found["mcp"]["identity"]
        (workspace / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))
        assert (await discover(backend))["mcp"]["identity"] != old
    finally:
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_http_mcp_uses_offline_sandbox_with_separate_remote_connection(
    store, local, settings
):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "examples/mcp_server.py",
        "--http",
        "--port",
        str(port),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    manager = SandboxManager(store)
    try:
        async with asyncio.timeout(15):
            while True:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.get(f"http://127.0.0.1:{port}/mcp")
                    break
                except httpx.ConnectError:
                    if process.returncode is not None:
                        raise AssertionError((await process.stderr.read()).decode())
                    await asyncio.sleep(0.1)
        config = {"mcpServers": {"remote": {"url": f"http://127.0.0.1:{port}/mcp"}}}
        (Path(local.repository) / ".mcp.json").write_text(json.dumps(config))
        backend = await manager.ensure(local.id)
        found = await discover(backend)
        store.mutate(
            local.id,
            lambda s, e: (
                s.trust.update({"mcp": found["mcp"]["identity"]}),
                setattr(s.policy, "auto_allow", ["remote_*"]),
            ),
        )
        rid = Controls(store).send(local.id, "Add", "queue", "first")["run_id"]
        await Runner(
            settings, store, manager, model=one_tool("remote_add", {"a": 4, "b": 8})
        ).execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert "12" in str(run.receipts["operation-1"].result)
        assert not store.get(local.id).sandbox.network
    finally:
        if process.returncode is None:
            process.terminate()
        await process.wait()
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_native_skills_and_repo_context_are_loaded_only_after_trust(store, local, settings):
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    from pydantic_lab.runtime.extensions import load_extensions

    workspace = Path(local.repository)
    skill = workspace / ".agents/skills/code-review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(Path("examples/skills/code-review/SKILL.md").read_text())
    (skill / "support.txt").write_text("first version")
    (workspace / "AGENTS.md").write_text("Unique repository rule: explain tests before editing.")
    manager = SandboxManager(store)
    try:
        backend = await manager.ensure(local.id)
        capabilities, found = await load_extensions(store, local, backend, settings.state_dir)
        assert not capabilities
        store.mutate(
            local.id, lambda s, e: s.trust.update({k: v["identity"] for k, v in found.items()})
        )
        checked = []

        def response(messages, info):
            assert "Unique repository rule" in (info.instructions or "")
            if any(
                "Read the changed files and their tests" in str(p)
                for m in messages
                for p in m.parts
            ):
                checked.append(True)
                return ModelResponse(parts=[TextPart("Loaded native skill")])
            return ModelResponse(
                parts=[
                    ToolCallPart("load_capability", {"id": "code-review"}, tool_call_id="skill-1")
                ]
            )

        async def stream(messages, info):
            for p in response(messages, info).parts:
                if isinstance(p, TextPart):
                    yield p.content
                else:
                    yield {
                        0: DeltaToolCall(
                            name=p.tool_name,
                            json_args=p.args_as_json_str(),
                            tool_call_id=p.tool_call_id,
                        )
                    }

        rid = Controls(store).send(local.id, "Review", "queue", "skill")["run_id"]
        await Runner(
            settings, store, manager, model=FunctionModel(response, stream_function=stream)
        ).execute(local.id, rid)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert checked
        (skill / "support.txt").write_text("changed version")
        assert (await discover(backend))["skills"]["identity"] != found["skills"]["identity"]
    finally:
        await manager.destroy(local.id)
