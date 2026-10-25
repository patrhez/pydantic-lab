# Pydantic AI Coding Agent Lab Specification

Status: draft for owner review. The product decisions below were confirmed in conversation. Implementation defaults stay proposals until this document is approved.

## Document rules

This specification states required behavior. The learning guides explain the design. `implementation-status.md` records verified behavior. Call a feature implemented only after it has been verified. Keep code, tests, guides, and diagrams aligned in each feature change.

Write in English. Prefer short sentences, active voice, and standard technical terms. That is an ASD-STE100-style target, not a certification. Use Conventional Commits 1.0.0 for every commit. See the [documentation index](README.md) and [contribution rules](../CONTRIBUTING.md).

## Purpose

Build a standalone, readable lab that shows advanced Pydantic AI behavior through two coding-agent interfaces:

1. A minimal interactive terminal agent that operates on the user's actual local repository.
2. A web chat application backed by an API service and an agent service, deployed independently.

Both support coding tools, permissions, human approvals, execution receipts, execution checkpoints, queue and steer messages, context compaction, Agent Skills, MCP, and repository instructions. All repository content and product text must be English. Do not import runtime code from `agent-frameworks-lab` or `agent-platform`.

Prefer public framework capabilities to custom replacements. The first release does not include sub-agent delegation, multiple users, authentication flows, file rollback, a large slash-command catalog, or high-availability deployment.

## Confirmed architecture

```text
Browser -> API server -> durable application state in MySQL
              |                     ^
              | replay events       | claim work / record execution
              v                     |
             SSE                Agent server -> model provider
                                    |
                                    v
                           Per-session Docker sandbox
                                    |
                           Persistent session workspace

Redis: wake-up and notification hints; never authoritative state.
CLI: in-process runtime + framework local persistence + Docker bind mount.
```

Frontend, API server, agent server, MySQL, and Redis are separate local Docker deployments. MySQL and Redis use separate containers and persistent volumes as needed. Rebuilding the frontend or API must not restart the agent server or session sandboxes. Host-facing frontend and API ports bind to `127.0.0.1`. Infrastructure and agent-service interfaces stay internal.

- API: session lifecycle requests, user messages, approval decisions, queue/steer/stop controls, snapshots, and SSE replay. The API does not call the model and does not read or write the repository filesystem.
- Agent server application layer: scheduling, execution ownership, persistence, sandbox lifecycle, and runtime event adaptation.
- Agent runtime: the model/tool loop, framework capabilities, injected execution context, and framework events. It has no HTTP handlers and no session business rules.
- Sandbox manager: container and volume provisioning, reconnection, stopping, reconciliation, and cleanup. This role stays separate from the agent loop, even when both run in the agent-service process.
- MySQL: the authoritative store for server sessions, commands, messages, runs, approvals, receipts, events, sandbox bindings, and checkpoints.
- Redis: optional, used only to reduce latency. If a notification is missed, recover the work by querying MySQL.

Proposed implementation defaults: Python with uv, FastAPI for the HTTP services, React/TypeScript with Vite for the frontend, and Docker Compose for local deployment. Use one Python package with clear modules and a separate entry point per service. Do not add a generic shared framework. It would hide the learning path.

## Framework reuse and version verification

Before implementing a feature, pin compatible stable package versions and check their public APIs with small executable probes. Online documentation shows which concepts exist. It does not show that every API is present in the installed version.

| Responsibility | Preferred framework integration | Application responsibility |
| --- | --- | --- |
| Model/tool loop | Pydantic AI Agent | Wiring and limits |
| File and shell tools | Harness FileSystem and Shell | Policy decisions and event presentation |
| Isolation | Harness DockerSandbox | Container hardening and lifecycle |
| Checkpoints | Harness StepPersistence | Recovery policy and server MySQL StepStore adapter |
| Local persistence | Framework file/SQLite stores | Minimal control-state persistence where necessary |
| Approvals | Native deferred tools/approval APIs | Durable pending decisions, exact-call binding, invalidation |
| Compaction | Official context-management capabilities | Configuration and learning logs |
| Skills | Harness Skills | Trust selection and configuration |
| MCP | MCPToolset and configuration loaders | Trust, transport placement, policy and lifecycle |
| Repository instructions | Harness RepoContext | Trust boundary and loaded-file logging |

Use supported public extension points. Do not import private CLAI application internals. If a required behavior has no reusable public API, record the gap and add a narrow adapter. A missing API is not a reason to quietly weaken a confirmed behavior.

## Workspace and sandbox model

Use DockerSandbox for both modes. Tools run in the sandbox. Model requests and provider credentials stay in the controller or agent service.

### Local CLI

Bind-mount the explicitly selected real repository read-write at `/workspace`. Edits change the user's original files immediately. Do not clone or copy the repository. Use the container's toolchains, not the macOS toolchains. Keep container dependencies and caches separate from the host `.venv` and `node_modules` directories.

The CLI also supports a plain one-shot mode for noninteractive stdin or stdout. If a mutation or command needs approval, save the pending state, print a resume instruction, and exit with status `3`. Do not auto-allow approvals in noninteractive mode.

### Server

Each session owns one logical sandbox and one independent persistent workspace volume. Initialize it from a public Git URL and an explicitly resolved branch or commit, and record the resolved commit. Release one does not need private-repository credentials or a push workflow.

Store `session_id`, the logical `sandbox_id`, the container reference, the volume reference, the image and configuration identity, and the lifecycle state in MySQL. Docker labels help reconciliation. They do not replace the binding record. A run finds its workspace through the session binding.

Stop idle containers after a configurable timeout. A session waiting for approval is idle when no operation is executing. Keep the workspace volume. Close stdio MCP transports before stopping the container, and reconnect them when the sandbox is used again. After an agent-service restart, reattach to the existing sandbox. If the container is missing, rebuild it from the recorded image and configuration and the existing volume. Files in the volume survive. Processes and container-layer changes are not part of that recovery. Deleting a session requires explicit confirmation in the UI, then cleanup of its sandbox and workspace. While a run is active or waiting for approval, the user must Stop it before Delete becomes available. Record cleanup that fails so it can be retried.

### Execution environment

Provide a development image with Python, uv, Node.js, Git, and ripgrep. Allow a user-selected image and explicit initialization commands. Full Dev Container compatibility is out of scope.

Initialization may use the network to clone the repository and install dependencies. Initialization commands stay under policy control and are logged. During provisioning, show pending setup approvals with active Allow Once and Reject Once controls while chat stays disabled. Rejection ends initialization as failed without executing that command. Persist setup requests across refresh and restart. Normal execution starts with no network. A user can turn session networking on explicitly. Apply the Docker network configuration and verify it before the next operation. If that requires a new container, recreate it and keep the volume. A database flag by itself does not change the network. Allow a network change only when no run is active and no approval is pending. Report the new state only after the Docker network has been applied and verified. Do not automatically fall back to host execution.

Run tool containers as non-privileged, with resource limits and restricted mounts. Do not expose the Docker socket, controller state, or provider credentials to tool containers. Only the trusted sandbox manager may control Docker. Document that access as a privileged control-plane capability.

Proposed stdio bridge: the official MCP client starts an argv-based `docker exec -i` transport, and the MCP program itself runs inside the session sandbox. With the pinned framework, verify cancellation, process cleanup, and restart behavior. Do not run repository-configured stdio programs directly in the agent-service container.

## Scheduling and user controls

A session has at most one active run, including a run that is waiting for approval. Different sessions may run at the same time, up to a configurable agent-service concurrency limit. Release one does not need multiple agent-service replicas. Restart recovery must not create a second local owner for the same execution.

- **Queue:** persist a FIFO follow-up that becomes a new run after the active run finishes.
- **Steer:** keep the current logical run, record the follow-up durably, and inject it before the next model request at a safe boundary. Let an executing tool finish first. Never inject a message in the middle of a tool-call/result pair.
- **Steer during approval:** invalidate every pending approval that has not executed, for the plan being replaced. Resolve or cancel the pending framework protocol to match. Inject the steer and let the model plan again. Reject stale approval submissions. Show this public-API path with a probe before treating the implementation as complete.
- **Stop:** cancel the active run, invalidate pending approvals, and try to stop commands that are still executing. Keep queued messages, and pause scheduling until the user chooses Continue.
- **Default input mode:** Queue is the default while a run is active. The user must explicitly select Steer. The CLI shows the mode and uses Tab to switch it. The Web UI uses a Queue/Steer segmented control. While scheduling is paused after Stop, Queue may append a message but must not start it before Continue.
- **CLI interrupt:** at an idle empty prompt, Ctrl+C exits. With an idle draft, the first Ctrl+C clears the draft and a second exits. During a run or approval, the first Ctrl+C sends the durable Stop control. A second Ctrl+C within three seconds exits the process. In stopped, completed, failed, or unknown-outcome states, Ctrl+C exits after rendering the current state.
- **CLI resume:** `resume` selects the latest recoverable session for the current repository. If several qualify, it lists IDs and requires `resume <id>`.
- A stopped or interrupted run leaves completed filesystem effects in place. An operation with no confirmed outcome follows the unknown-outcome policy.

Use durable message identities and consumption markers so a retry does not deliver the same message or steer injection twice. Keep queued turns when steer is applied. Continue resumes queued work. It does not revive a cancelled run. Keep partial assistant output for display and mark it stopped. Do not send it back to the model as a completed assistant answer. Persist the paused scheduling state. A browser refresh or reconnect must keep pending controls. Test Stop, steer, and approval races as explicit state transitions.

## Permissions and approvals

Default policy: workspace reads are automatic. File mutations and commands need approval unless an explicit auto-allow rule covers them. Explicit denials and sandbox restrictions still apply after approval. Agent tools cannot change the active trusted policy.

Reuse the Shell executable allowlists, denylists, and operator controls. They are best-effort guardrails. They are not a parameter-level security engine. Do not build a complex shell parser. Allowing Python, uv, make, or test runners does not stop arbitrary code execution.

Add only the routing needed to choose auto-allow, request approval, or deny. Bind each decision to the exact operation identity and canonical arguments, and to a policy or configuration revision when one applies. Support Allow Once and Reject Once. Longer-lived permissions come from durable user configuration. Approval has no time-based expiry. It remains pending across restart until a decision, Stop, steer, or a policy/configuration revision change invalidates it.

An approval request must survive a controller restart. After a file edit is approved, check the target for conflicts. Do not quietly overwrite a target that changed. Check how native deferred approvals interact with StepPersistence. Do not assume a message snapshot stores every pending control.

## Persistence and recovery

Use native StepPersistence snapshots, event records, and tool-effect tracking where the framework provides them. For the CLI, use the framework's local persistent backend, chosen during the API probe. Do not build a second checkpoint engine. Add application storage only for scheduling, approval, and sandbox-binding state that the framework does not store. Server checkpoints use a MySQL adapter that implements the supported store contract.

Recovery rules:

1. Restore queued messages, paused scheduling, and pending approvals.
2. Continue from the latest valid settled checkpoint. Do not replay tool effects that are already recorded.
3. An interrupted model request may be retried from that boundary. The retry can add provider cost.
4. A mutating operation or command that started without a confirmed receipt becomes `outcome_unknown`. Pause for inspection and an explicit user decision. Offer exactly Continue without retry, Retry once, and Abort. Continue gives the model an honest result that says the outcome was unknown and the user inspected the workspace. Retry once requires a fresh policy check and a duplicate-effect warning. Abort cancels the run and preserves completed effects. Never re-run it without that decision.
5. A recorded effect that lacks a complete model-facing result must be reconciled. The effect ledger alone does not show that the framework can safely continue the pending tool batch.

A checkpoint snapshot is not a copy of the filesystem. A filesystem change and the MySQL or local write that records it are not one transaction. StepPersistence and execution receipts do not guarantee exactly-once execution. Do not add a workflow engine only to store conversations.

## Events, logs, and diff

Approvals, execution receipts, checkpoints, recovery, steering, and compaction need structured records that can be traced, plus readable console output. Correlate session, run, tool-call, approval, and checkpoint identities. Show the saved or restored boundary, operation state, decision source, duration, and a safe summary of the result. Do not log credentials.

Write server-visible application events to MySQL before publishing Redis hints or serving SSE. Support ordered replay and reconnect cursors. The browser builds its view from snapshots and committed events, not from drafts that live in one process. Commit buffered assistant text before SSE delivery when a Markdown block closes, the buffer reaches 2 KiB, or its oldest text has waited 100 ms, whichever comes first. Flush remaining text before completion, Stop, failure, or an approval/tool boundary is recorded. Refresh and reconnect can then replay the same partial answer.

Diff is a presentation of current files. It is not a separate durable data requirement:

- Use framework edit events for the live view of a single edit.
- Build an approval preview from the pending edit arguments and the current content. Check the target again when the user approves.
- Compute the current workspace Git diff on demand. Include staged and unstaged changes, and handle untracked files separately.
- Label workspace differences accurately. Changes the user made before the run, or while it was running, are not all the agent's work.
- Do not add a historical diff store, and do not promise replay of each past edit.
- Framework snapshots or pending arguments may already contain source text. That is separate from copying a derived diff into application event storage.

The [CLI interaction specification](cli-interactions.md), [Web interaction specification](web-interactions.md), and [visual design specification](visual-design.md) define the planned controls, layouts, state feedback, and acceptance criteria. The interfaces use Queue as the active-run default, explicit Steer, Stop/Continue, Allow Once/Reject Once, on-demand diff, trust review, and recovery decisions. New approval cards preserve the current focus. Move focus into a card only after an explicit review action. The CLI keeps a minimal command set. The Web UI keeps session list, chat workspace, and inspector views. No large slash-command system.

## Context management

Include context compaction in release one. Prefer official capabilities and a configurable threshold checked before each request. Keep recent turns and valid tool-call/result pairs. Summarize older context. Keep the original conversation records, save the effective context after compaction for recovery, and log why compaction ran plus the before and after size, or the usage data the framework provides. If that figure is an estimate, record it as an estimate.

## Skills, MCP, and repository instructions

Use native Skills discovery and progressive loading, official MCP configuration and toolsets, and RepoContext. Disable sub-agent delegation.

User-managed configuration is trusted. Discover repository-provided configuration, and leave it inactive until the user explicitly trusts it. Trust is durable for the single local user, per repository identity, extension category, and relevant content identity. Grant Skills, MCP configuration, and repository instructions separately. Trust is a separate decision from tool-execution approval. Record the content identity, and drop trust when the relevant trusted configuration changes. Skill support files change behavior too. Define trust over the package content. Hashing only `SKILL.md` would treat bundled scripts as if they could not change.

Prefer a reusable public trust component when one exists. Official CLAI has a repository MCP trust workflow in its application. That workflow does not mean the framework loaders expose the same API. Skills exposure filters choose catalog entries. They do not control filesystem access. Repository instructions and trusted skills cannot change application permissions.

Support stdio and Streamable HTTP MCP. Stdio programs run in the matching sandbox. Remote HTTP connections start from the agent service and use separately configured destinations. An offline tool sandbox does not isolate those remote MCP services, and it does not take them offline. Apply policy, approvals, receipts, and logging to MCP tools. Tool annotations do not grant permission by themselves. Release one does not need an OAuth setup UI, an MCP marketplace, or a configuration editor. Include a small deterministic MCP example for demonstrations and integration tests.

## Test and delivery requirements

Run unit and integration tests that exercise the behavior. Mocks of the implementation are not enough. Include:

- Policy decisions, exact approval binding, explicit denials, stale edits, and stale approvals.
- Queue FIFO, steer at a boundary, steering during approval, Stop/Continue, duplicate requests, and control races.
- Actual framework model/tool loops with deterministic test models and real Docker execution.
- Local bind-mount edits that change the real test workspace, with containment and network checks.
- Independent server session workspaces and configurable concurrency across sessions.
- MySQL persistence, Redis notification loss, SSE reconnect and replay, and browser refresh.
- Process restart at approval, at a settled checkpoint, and at an uncertain execution boundary.
- Sandbox stop and restart, container recreation with the volume kept, and cleanup reconciliation.
- Context compaction that keeps a valid tool protocol and restores the effective context.
- Skills trust and loading, repository instructions, and both MCP transports with policy enforcement.
- Frontend interaction tests, and checks that services can be rebuilt and restarted independently.

Run a bounded live DeepSeek smoke test with the API key and base URL configured in `~/.zshrc`. Read only supported literal assignments. Do not execute the shell file, and do not print secrets. Keep credentials out of Git. Record the actual versions, commands, results, skipped checks, and material limits. If a check did not run, say so. Do not report it as passed.

## Review and implementation sequence

1. The owner reviews this specification. Do not start feature implementation before approval.
2. Verify and pin framework versions. Probe DockerSandbox, StepPersistence, deferred approvals and steering, compaction, Skills, RepoContext, and MCP transports. Record what can be reused and any incompatibilities.
3. Implement the minimal local runtime and CLI, with native persistence and learning logs.
4. Implement server persistence and scheduling, the independent services, per-session sandboxes, and the web interface.
5. Finish the unit, integration, container, browser, restart, and live-provider checks. Document the learning paths and the known limits.

The sibling repositories are architectural references only. Keep the implementation as small and readable as the confirmed behavior allows.

## Learning documents

- [Architecture](architecture.md)
- [Decisions](decisions.md)
- [CLI agent loop](cli-agent-loop.md)
- [CLI interactions](cli-interactions.md)
- [Web interactions](web-interactions.md)
- [Visual design](visual-design.md)
- [Execution](execution.md)
- [Persistence](persistence.md)
- [Sandboxes](sandboxes.md)
- [Framework integrations](integrations.md)
- [Verification](verification.md)
- [Implementation status](implementation-status.md)

## Primary references

- https://pydantic.dev/docs/ai/harness/
- https://pydantic.dev/docs/ai/harness/docker-sandbox/
- https://pydantic.dev/docs/ai/harness/step-persistence/
- https://pydantic.dev/docs/ai/harness/filesystem/
- https://pydantic.dev/docs/ai/harness/shell/
- https://pydantic.dev/docs/ai/harness/skills/
- https://pydantic.dev/docs/ai/harness/repo-context/
- https://pydantic.dev/docs/ai/mcp/client/
- https://pydantic.dev/docs/ai/capabilities/overview/
