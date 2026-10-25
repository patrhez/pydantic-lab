"""Discover repository extensions without activating them before trust."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile

from fastmcp import Client
from pydantic_ai.mcp import MCPToolset, load_mcp_toolsets
from pydantic_ai.workspaces import Workspace
from pydantic_ai_harness import RepoContext, Skills

from pydantic_lab.storage.control import Conflict

ROOTS = {
    "skills": [".agents/skills", ".claude/skills"],
    "instructions": ["AGENTS.md", "CLAUDE.md"],
    "mcp": [".mcp.json"],
}


async def discover(backend):
    workspace = Workspace(backend)
    categories = {}
    for category, roots in ROOTS.items():
        contents = {}
        for root in roots:
            result = await backend.run(["find", root, "-type", "f"], timeout=10)
            links = await backend.run(["find", root, "-type", "l"], timeout=10)
            if links.stdout.strip():
                raise Conflict("Symlinked extension files cannot be trusted")
            for name in sorted(result.stdout.splitlines()):
                if len(contents) >= 200:
                    raise Conflict("Extension package exceeds 200 files")
                path = name.removeprefix("./")
                resolved = await workspace.realpath(path)
                if not resolved.startswith("/workspace/"):
                    raise Conflict("Extension file is outside the workspace")
                data = await workspace.read_bytes(path)
                if len(data) > 1_000_000:
                    raise Conflict("Extension file exceeds 1 MB")
                contents[path] = data.decode("utf-8")
        if contents:
            signature = hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()
            categories[category] = {
                "identity": signature,
                "files": list(contents),
                "contents": contents,
            }
    return categories


async def load_extensions(store, session, backend, state_dir):
    found = await discover(backend)
    active = []
    for category, package in found.items():
        if session.trust.get(category) != package["identity"]:
            continue
        if category == "skills":
            active.append(
                Skills(ROOTS[category], missing_directories="skip", duplicate_names="keep_first")
            )
        elif category == "instructions":
            active.append(RepoContext(filenames=ROOTS[category], nested_traversal=False))
        else:
            config = json.loads(package["contents"][".mcp.json"])
            servers = config.get("mcpServers", config.get("servers", {}))
            translated = {}
            for name, definition in servers.items():
                definition = dict(definition)
                if "command" in definition:
                    environment = definition.pop("env", {})
                    env_args = []
                    for key, value in environment.items():
                        if "${" in value:
                            if value.startswith("${") and value.endswith("}"):
                                value = os.environ.get(value[2:-1], "")
                            else:
                                raise Conflict(
                                    "Use complete ${NAME} references for MCP environment values"
                                )
                        env_args.extend(["--env", f"{key}={value}"])
                    definition = {
                        "command": "docker",
                        "args": [
                            "exec",
                            "-i",
                            *env_args,
                            session.sandbox.container,
                            definition["command"],
                            *definition.get("args", []),
                        ],
                    }
                translated[name] = definition
            # The official loader remains the authority for transport configuration.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=state_dir) as handle:
                json.dump({"mcpServers": translated}, handle)
                handle.flush()
                loaded = load_mcp_toolsets(handle.name)
                for index, (toolset, (name, definition)) in enumerate(
                    zip(loaded, translated.items())
                ):
                    if "command" in definition:
                        # Use a public pre-built client so framework adaptation retains
                        # the handshake mode and allows cold container imports to finish.
                        toolset.wrapped.client.transport.keep_alive = False
                        client = Client(
                            toolset.wrapped.client.transport, mode="legacy", init_timeout=30
                        )
                        loaded[index] = MCPToolset(client, id=name).prefixed(name)
                active.extend(loaded)
    return active, found
