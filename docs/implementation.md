# Implementation Walkthrough

This guide maps the design to working source. Read it beside the [CLI loop diagram](cli-agent-loop.md) and [architecture diagram](architecture.md).

## Source map

| File | Responsibility |
| --- | --- |
| [agent.py](../src/pydantic_lab/runtime/agent.py) | Compose native capabilities and commit streamed text |
| [policy.py](../src/pydantic_lab/runtime/policy.py) | Permission routing, exact approvals, steer boundary, and receipts |
| [runner.py](../src/pydantic_lab/application/runner.py) | Logical runs, native continuation, recovery, and cancellation |
| [controls.py](../src/pydantic_lab/application/controls.py) | Atomic Queue, Steer, Stop, Continue, and recovery decisions |
| [worker.py](../src/pydantic_lab/application/worker.py) | Session scheduling, setup, lifecycle actions, and internal service |
| [inspection.py](../src/pydantic_lab/application/inspection.py) | Transient workspace and proposed-edit inspection |
| [control.py](../src/pydantic_lab/storage/control.py) | Session transactions, request deduplication, and display events |
| [steps.py](../src/pydantic_lab/storage/steps.py) | Public MySQL StepStore adapter and checkpoint logs |
| [manager.py](../src/pydantic_lab/sandbox/manager.py) | Docker bindings, resource limits, mounts, Git clone, and lifecycle |
| [extensions.py](../src/pydantic_lab/runtime/extensions.py) | Content discovery, trust selection, and native extension loading |
| [main.py](../src/pydantic_lab/cli/main.py) | Concurrent terminal input, commands, and rendering |
| [server.py](../src/pydantic_lab/api/server.py) | Public HTTP routes, snapshots, inspection proxy, and SSE |
| [App.tsx](../frontend/src/App.tsx) | Session workspace, controls, drafts, and replay connection |

## Native loop and application loop

`Agent.run()` owns model requests and tool dispatch. The Runner does not reproduce that loop. It starts a native run, observes its result, and supplies deferred decisions when required.

One logical run can have several native run IDs. An approval wait ends a native segment with `DeferredToolRequests`. After a decision, the Runner supplies native messages and `DeferredToolResults` to a new segment. The session and logical run IDs remain the same.

The scheduler is separate. Queue creates later logical runs. Steer attaches input to the active run. `before_model_request` consumes steer and saves the effective history in one control transaction. An executing tool finishes before that boundary.

During approval, Steer expires the old operations. Their resumed tool calls receive cancellation results from the permission adapter. The framework then has a complete tool protocol before it receives the steer message. The old operation does not execute.

## Approval and receipts

`wrap_tool_execute` checks the workspace, policy, trusted content, and exact operation identity. Reads are automatic. Mutations, commands, and MCP operations need approval unless an explicit rule covers the tool.

The adapter raises native `ApprovalRequired`. It saves the approval ID, canonical argument digest, policy revision, and file hash. After Allow Once, it checks those values again. A changed file requires a new proposal.

The application receipt spans native segments. Native effect records are scoped to a native run. That difference requires a small logical-run receipt for deduplication and recovery. A completed receipt returns its saved result instead of repeating an effect.

A started receipt without a result is uncertain. File changes and MySQL transactions cannot commit together. The next owner stops the old container, marks the operation `outcome_unknown`, and pauses execution. Continue without retry supplies an honest unknown result. Retry requires a new approval. Abort leaves files unchanged by recovery.

Normal service shutdown detaches a pending run. Only a committed Stop cancels it and pauses the queue. The tests cover both graceful detach and SIGKILL.

## Checkpoints and context

The CLI uses native `SqliteStepStore` in `framework.db`. Small application controls live in `control.db`. Both files are under the configured state directory.

The server uses `DatabaseStepStore`, which implements the public StepStore protocol. Native dataclasses are validated and stored as JSON in MySQL. Events and snapshots use atomic, unique-key upserts that preserve the first payload. Effect upserts replace their result. This avoids locking a missing row before insertion, which can deadlock concurrent InnoDB writers. `ObservedStepStore` delegates persistence and emits learning logs after a snapshot commits.

Recovery compares the native snapshot time with the saved application frontier. It selects the newer valid history. Approval state and tool receipts remain separate from model context.

`LoggedCompaction` delegates to native `SummarizingCompaction`. It keeps recent messages and valid tool pairs, and logs estimated sizes before and after summarization. The original event and native records remain available. The default threshold is 24,000 estimated tokens.

## Storage and service boundaries

The control schema has `sessions`, `events`, `requests`, and `extension_trust` tables. A session payload holds runs, approvals, receipts, and the sandbox binding. A row lock serializes its controls. `framework_records` stores native runs, events, snapshots, and effects. This small schema favors readability over large-history query performance.

The API commits user intent. The agent scheduler polls for eligible work. Redis publishes post-commit hints; polling remains authoritative. The current implementation polls directly rather than subscribing to those hints.

SSE reads committed MySQL events with a global increasing cursor. A snapshot captures session state and cursor together. The browser resumes after that cursor and ignores repeated IDs. Assistant text and its display event commit in one transaction. A timer flushes text within 100 ms, even if provider output pauses.

Read-only inspection uses an internal HTTP endpoint on the agent server. The API proxies it. Current Git diff and proposed-edit diff stay in the response and browser memory. They do not enter MySQL display records. Lifecycle changes remain durable queued actions.

## Session and sandbox binding

A session owns one stable sandbox ID. Container labels, a stored container reference, and stable volume names connect it to Docker resources. A replacement container uses the same server workspace volume.

The manager uses public `DockerSandboxBackend`, the backend supplied by `DockerSandbox`. Explicit backend ownership lets it stop and reattach containers without destroying session files. Native tools receive that backend through `workspace=`.

The CLI mounts the selected real repository at `/workspace`. Separate named volumes cover `.venv` and `node_modules`. Linux dependencies do not reuse host environments and survive container restart. Server workspaces use a named volume at `/workspace` plus the same dependency separation.

Tool containers run without root privileges, dropped capabilities, Docker access, or provider keys. Limits are 2 CPUs, 2 GB RAM, and 256 processes. Setup uses network access. Normal execution starts with Docker networking disabled. Explicit network changes recreate the container and preserve its volumes.

## Skills and MCP

Copy the [sample skill](../examples/skills/code-review/SKILL.md) to `.agents/skills/code-review/SKILL.md` in a test workspace. Use CLI `/trust` or Web Extensions to inspect and trust it. Native Skills exposes its catalog and `load_capability` loads its instructions progressively.

Trust covers each category's complete package contents, including skill support files. A registry reuses that decision for the same repository identity and content signature. Native RepoContext loads trusted root instruction files. Nested instruction traversal is disabled in this release. Discovery does not execute configuration.

Copy [mcp.json](../examples/mcp.json) to `.mcp.json` in a test workspace. The example stdio service needs FastMCP inside the sandbox. Install it in the sandbox's managed environment, then use:

```json
{
  "mcpServers": {
    "example": {
      "command": "/workspace/.venv/bin/python",
      "args": ["/workspace/examples/mcp_server.py"]
    }
  }
}
```

For server setup, approve `uv venv /workspace/.venv` and `uv pip install --python /workspace/.venv/bin/python 'fastmcp-slim[server]==4.1.3'` as separate initialization commands. For a local demonstration, a custom sandbox image can supply the dependency. The integration test uses the application image as its tool image, without mounting its Docker socket or provider environment.

The official MCP loader selects transports and prefixes tool names. Stdio is bridged through `docker exec -i` in the trusted controller. A public FastMCP Client uses a 30-second initialization timeout and legacy handshake for stdio compatibility. Its process closes between connections. HTTP uses the native loader directly.

For Streamable HTTP, use `{"mcpServers":{"remote":{"url":"http://host.docker.internal:8765/mcp"}}}` in Compose. Run the example with `uv run python examples/mcp_server.py --http` on the host. A local CLI uses `127.0.0.1` instead. HTTP destinations belong to the trusted MCP configuration; sandbox network controls do not restrict them. Never place literal credentials in repository configuration.

## Learning path

1. Run a deterministic CLI read and follow checkpoint and receipt logs.
2. Run `--demo --demo-tool write_file` in a temporary repository. Resume and approve the pending operation.
3. Change the target before approval. Observe conflict refusal.
4. Send Steer during approval. Observe invalidation and safe protocol continuation.
5. Run the recovery tests and inspect the counter that must not increment twice.
6. Run Compose and rebuild only the API and frontend during an approval wait.
7. Inspect the MCP and compaction tests beside their public framework adapters.

See [verification](verification.md) for reproducible commands and [implementation status](implementation-status.md) for evidence and limits.
