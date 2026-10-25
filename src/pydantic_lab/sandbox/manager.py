"""Trusted Docker lifecycle control. No Docker socket is exposed to tools."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import time
from urllib.parse import urlparse

from pydantic_ai.workspaces import WorkspaceRef
from pydantic_ai_harness.docker_sandbox import DockerSandboxBackend

from pydantic_lab.storage.control import Conflict, ControlStore


async def docker(*args: str, check=True) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), 180)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    if check and process.returncode:
        raise RuntimeError(err.decode(errors="replace")[-2000:])
    return out.decode().strip()


def validate_repository(url: str):
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 80, 443}
    ):
        raise Conflict("Enter a public HTTP(S) Git URL without credentials")
    for address in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise Conflict("The Git host must resolve to public addresses")


class SandboxManager:
    def __init__(self, store: ControlStore):
        self.store = store
        self.locks: dict[str, asyncio.Lock] = {}

    async def ensure(
        self, sid: str, *, initialize_network=False, network_override=None
    ) -> DockerSandboxBackend:
        async with self.locks.setdefault(sid, asyncio.Lock()):
            session = self.store.get(sid)
            binding = session.sandbox
            names = await docker(
                "ps", "-a", "--filter", f"label=lab.sandbox={binding.id}", "--format", "{{.Names}}"
            )
            container = names.splitlines()[0] if names else None
            network = (
                (initialize_network or binding.network)
                if network_override is None
                else network_override
            )
            if container:
                info = json.loads(await docker("inspect", container))[0]
                actual_online = info["HostConfig"]["NetworkMode"] != "none"
                if actual_online != network:
                    await docker("rm", "-f", container)
                    container = None
            dependency_volumes = [f"lab-venv-{binding.id}", f"lab-node-{binding.id}"]
            for dependency in dependency_volumes:
                await docker("volume", "create", "--label", f"lab.sandbox={binding.id}", dependency)
            if container:
                await docker("start", container)
                await docker("exec", "--user", "0", container, "chmod", "1777", "/run/pydantic-ai")
                backend = DockerSandboxBackend(ref=WorkspaceRef(provider="docker", id=container))
            else:
                if session.mode == "server":
                    volume = binding.volume or f"lab-workspace-{binding.id}"
                    await docker("volume", "create", "--label", f"lab.sandbox={binding.id}", volume)
                    mount = f"{volume}:/workspace"
                    user = "1000:1000"
                else:
                    volume = None
                    mount = f"{session.repository}:/workspace"
                    user = f"{os.getuid()}:{os.getgid()}"
                backend = DockerSandboxBackend(
                    image=binding.image,
                    allow_internet_access=network,
                    docker_args=[
                        "--volume",
                        mount,
                        "--label",
                        f"lab.sandbox={binding.id}",
                        "--user",
                        user,
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--memory",
                        "2g",
                        "--cpus",
                        "2",
                        "--pids-limit",
                        "256",
                        "--volume",
                        f"{dependency_volumes[0]}:/workspace/.venv",
                        "--volume",
                        f"{dependency_volumes[1]}:/workspace/node_modules",
                    ],
                )
            try:
                await backend.working_dir()
            finally:
                if backend.ref:

                    def save(s, emit):
                        s.sandbox.container = backend.ref.id
                        if s.mode == "server":
                            s.sandbox.volume = f"lab-workspace-{s.sandbox.id}"
                        s.sandbox.last_used = time.time()
                        s.sandbox.state = "running"
                        emit("sandbox.attached", container=backend.ref.id, network=network)

                    self.store.mutate(sid, save)
            return backend

    async def clone(self, sid: str):
        session = self.store.get(sid)
        validate_repository(session.repository)
        backend = await self.ensure(sid, initialize_network=True)
        revision = session.commit or session.branch or "HEAD"
        if revision.startswith("-") or any(c in revision for c in ("\x00", "\n")):
            raise Conflict("Invalid Git revision")
        for command in (
            ["git", "init", "."],
            ["git", "remote", "remove", "origin"],
            ["git", "remote", "add", "origin", session.repository],
            ["git", "-c", "protocol.file.allow=never", "fetch", "--depth=1", "origin", revision],
            ["git", "checkout", "--detach", "FETCH_HEAD"],
        ):
            result = await backend.run(command, timeout=120)
            if result.exit_code and command[:4] != ["git", "remote", "remove", "origin"]:
                raise RuntimeError(result.stderr[-2000:])
        result = await backend.run(["git", "rev-parse", "HEAD"], timeout=10)
        self.store.mutate(sid, lambda s, emit: setattr(s, "commit", result.stdout.strip()))

    async def stop(self, sid: str):
        session = self.store.get(sid)
        if session.sandbox.container:
            await docker("stop", "--time", "2", session.sandbox.container, check=False)
        self.store.mutate(
            sid, lambda s, emit: (setattr(s.sandbox, "state", "stopped"), emit("sandbox.stopped"))
        )

    async def destroy(self, sid: str, *, volume=True):
        session = self.store.get(sid)
        if session.sandbox.container:
            await docker("rm", "-f", session.sandbox.container, check=False)
        if volume:
            for dependency in (f"lab-venv-{session.sandbox.id}", f"lab-node-{session.sandbox.id}"):
                await docker("volume", "rm", dependency, check=False)
            if session.sandbox.volume:
                await docker("volume", "rm", session.sandbox.volume)
        self.store.mutate(
            sid,
            lambda s, emit: (
                setattr(s.sandbox, "container", None),
                setattr(s.sandbox, "state", "stopped"),
                emit("sandbox.removed"),
            ),
        )

    async def diff(self, sid: str):
        backend = await self.ensure(sid)
        result = {}
        for name, command in {
            "staged": ["git", "diff", "--cached", "--no-ext-diff", "--no-textconv"],
            "unstaged": ["git", "diff", "--no-ext-diff", "--no-textconv"],
            "untracked": ["git", "ls-files", "--others", "--exclude-standard"],
        }.items():
            out = await backend.run(command, timeout=10)
            result[name] = out.stdout[:200_000]
        return result
