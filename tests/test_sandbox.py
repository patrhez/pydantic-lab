from pathlib import Path

import pytest

from pydantic_lab.sandbox.manager import SandboxManager, docker


@pytest.mark.integration
async def test_local_dependency_mount_survives_restart_without_touching_host_env(store, local):
    workspace = Path(local.repository)
    (workspace / ".venv").mkdir()
    (workspace / ".venv/host-marker").write_text("host")
    manager = SandboxManager(store)
    try:
        backend = await manager.ensure(local.id)
        result = await backend.run(["sh", "-c", "test ! -e .venv/host-marker && echo isolated"])
        assert result.stdout.strip() == "isolated"
        result = await backend.run(["uv", "venv", "/workspace/.venv"], timeout=20)
        assert result.exit_code == 0, result.stderr
        result = await backend.run(["sh", "-c", "echo cached > .venv/container-marker"])
        assert result.exit_code == 0, result.stderr
        await manager.stop(local.id)
        restored = await manager.ensure(local.id)
        result = await restored.run(["cat", ".venv/container-marker"])
        assert result.stdout.strip() == "cached"
        assert (workspace / ".venv/host-marker").read_text() == "host"
        assert not (workspace / ".venv/container-marker").exists()
    finally:
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_server_workspace_volume_survives_container_replacement(store, local):
    store.mutate(local.id, lambda s, e: setattr(s, "mode", "server"))
    manager = SandboxManager(store)
    try:
        first = await manager.ensure(local.id)
        await first.run(["sh", "-c", "echo preserved > data.txt"])
        original = store.get(local.id).sandbox.container
        await manager.destroy(local.id, volume=False)
        second = await manager.ensure(local.id)
        assert second.ref.id != original
        result = await second.run(["cat", "data.txt"])
        assert result.stdout.strip() == "preserved"
        state = await docker("inspect", "--format", "{{.HostConfig.NetworkMode}}", second.ref.id)
        assert state == "none"
    finally:
        await manager.destroy(local.id)
