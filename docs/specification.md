# Pydantic AI Coding Agent Lab Specification

Status: Draft for owner review. Product decisions below have been confirmed in conversation; implementation defaults remain proposals until this document is approved.

## Document rules

This specification defines required behavior. Learning guides explain the design; `implementation-status.md` records verified behavior. Do not describe a planned feature as implemented. Keep code, tests, guides, and diagrams aligned in each feature change.

Use English and mostly ASD-STE100-inspired prose: short sentences, active voice, and standard technical terms. This is a writing target, not certified compliance. Use Conventional Commits 1.0.0 for every commit. See the [documentation index](README.md) and [contribution rules](../CONTRIBUTING.md).

## Purpose

Build a standalone, readable lab that demonstrates advanced Pydantic AI behavior through two coding-agent interfaces:

1. A minimal interactive terminal agent operating on the user's actual local repository.
2. A web chat application backed by independently deployed API and agent services.

Both support coding tools, permissions, human approvals, execution receipts, execution checkpoints, queue and steer messages, context compaction, Agent Skills, MCP, and repository instructions. All repository content and product text must be English. Do not import runtime code from `agent-frameworks-lab` or `agent-platform`.

This lab prioritizes public framework capabilities over custom replacements. It does not implement sub-agent delegation, multiple users, authentication flows, file rollback, a large slash-command catalog, or high-availability deployment in the first release.

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

Frontend, API server, agent server, MySQL, and Redis are separate local Docker deployments. MySQL and Redis use separate containers and persistent volumes as appropriate. Frontend/API rebuilds must not restart the agent server or session sandboxes. Host-facing frontend/API ports bind to `127.0.0.1`; infrastructure and agent-service interfaces remain internal.

- API: session lifecycle requests, user messages, approval decisions, queue/steer/stop controls, snapshots, and SSE replay. No model calls or repository filesystem access.
- Agent server application layer: scheduling, execution ownership, persistence, sandbox lifecycle, and runtime event adaptation.
- Agent runtime: model/tool loop, framework capabilities, injected execution context, and framework events. No HTTP handlers or session business rules.
- Sandbox manager: container/volume provisioning, reconnection, stopping, reconciliation, and cleanup. This is separate from the agent loop even if deployed in the agent-service process.
- MySQL: authoritative server sessions, commands, messages, runs, approvals, receipts, events, sandbox bindings, and checkpoints.
- Redis: optional latency optimization; missed notifications must be recoverable by querying MySQL.

Proposed implementation defaults: Python with uv, FastAPI for HTTP services, React/TypeScript with Vite for the frontend, Docker Compose for local deployment. Use one Python package with clear modules and separate service entrypoints; do not create a generic shared framework that obscures the learning path.

## Framework reuse and version verification

Before feature implementation, pin compatible stable package versions and verify their public APIs with small executable probes. Current online documentation is evidence of available concepts, not proof that every API exists in an installed version.

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

Use supported public extension points. Do not import private CLAI application internals. If a requested behavior lacks a reusable public API, document the gap and add a narrow adapter. A missing API must not silently weaken confirmed behavior.

## Workspace and sandbox model

Use DockerSandbox for both modes. Tool execution takes place in the sandbox; model requests and provider credentials stay in the controller/agent service.

### Local CLI

Bind-mount the explicitly selected real repository read-write at `/workspace`. Edits immediately affect the user's original files; do not clone or copy the repository. Use container toolchains rather than macOS toolchains. Keep container dependencies and caches separate from host `.venv` and `node_modules` directories.

### Server

Each session owns one logical sandbox and one independent persistent workspace volume. Initialize it from a public Git URL and an explicitly resolved branch/commit; record the resolved commit. No private-repository credentials or push workflow is required in release one.

Persist `session_id`, logical `sandbox_id`, container reference, volume reference, image/configuration identity, and lifecycle state in MySQL. Docker labels support reconciliation but do not replace the binding record. Runs resolve their workspace through their session binding.

Stop idle containers after a configurable timeout, including sessions waiting for approval when no operation is executing. Keep their workspace volumes. Close stdio MCP transports before stopping and reconnect them on reuse. Reattach after agent-service restarts. Rebuild a missing container from its recorded image/configuration and existing volume. Files in the volume survive; processes and container-layer changes are not a recovery guarantee. Session deletion includes explicit UI confirmation and cleanup of its sandbox/workspace, with retryable cleanup state.

### Execution environment

Provide a development image containing Python, uv, Node.js, Git, and ripgrep. Permit a user-selected image and explicit initialization commands; full Dev Container compatibility is out of scope.

Initialization may use network access for clone and dependency installation. Initialization commands remain policy-controlled and logged. Normal execution defaults to no network; a user may explicitly enable session networking. Apply and verify the actual Docker network configuration before the next operation, recreating the container with its retained volume if required. A database flag alone is insufficient. Do not automatically fall back to host execution.

Configure non-privileged tool containers, resource limits, and restricted mounts. Do not expose the Docker socket, controller state, or provider credentials to tool containers. Docker control access belongs only to the trusted sandbox manager and must be documented as a privileged control-plane capability.

Proposed stdio bridge: the official MCP client starts an argv-based `docker exec -i` transport, with the MCP program itself running inside the session sandbox. Verify cancellation, process cleanup, and restart behavior with the pinned framework. Do not run repository-configured stdio programs directly in the agent-service container.

## Scheduling and user controls

A session has at most one active run, including a run awaiting approval. Different sessions may run concurrently under a configurable agent-service concurrency limit. Release one need not support multiple agent-service replicas, but restart recovery must not accidentally create duplicate local execution ownership.

- **Queue:** persist a FIFO follow-up for a new run after the active run finishes.
- **Steer:** retain the current logical run, durably record a follow-up, and inject it before the next model request at a safe boundary. Let an executing tool finish first. Never inject midway through a tool protocol pair.
- **Steer during approval:** invalidate all pending, unexecuted approvals for the superseded plan, resolve/cancel the pending framework protocol consistently, inject the steer, and let the model re-plan. Reject stale approval submissions. The public-API strategy must be demonstrated before implementation is considered valid.
- **Stop:** cancel the active run, invalidate pending approvals, and best-effort stop executing commands. Preserve queued messages and pause scheduling until explicit Continue.
- A stopped or interrupted run does not roll back completed filesystem effects. An operation without a confirmed outcome follows the unknown-outcome policy.

Use durable message identities and consumption markers so retries do not duplicate messages or steer injections. Preserve queued turns when steer is applied. Continue resumes queued work; it does not revive a cancelled run. Preserve partial assistant output for display and mark it stopped; do not feed it back as a completed assistant answer. Persist paused scheduling state. A browser refresh or reconnect must not lose pending controls. Stop/steer/approval races require explicit state-transition tests.

## Permissions and approvals

Default policy: workspace reads are automatic; file mutations and commands require approval unless covered by an explicit auto-allow rule. Explicit denials and sandbox restrictions remain effective after approval. Agent tools cannot modify the active trusted policy.

Reuse Shell executable allowlists/denylists and operator controls. They are best-effort guardrails, not a parameter-level security engine. Do not build a complex shell parser or claim that allowing Python, uv, make, or test runners prevents arbitrary code execution.

Add only the routing needed to distinguish auto-allow, request approval, and deny. Bind each decision to an exact operation identity and canonical arguments, with a policy/configuration revision where applicable. Support Allow Once and Reject Once. Durable user configuration supplies longer-lived permissions.

An approval request must survive a controller restart. File edits require content-conflict checks after approval; a changed target must not be silently overwritten. Review how native deferred approvals interact with StepPersistence rather than assuming message snapshots serialize every pending control state.

## Persistence and recovery

Use native StepPersistence snapshots, event records, and tool-effect tracking where available. CLI uses the framework's local persistent backend, selected during the API probe; do not build a competing checkpoint engine. Supplement only missing scheduling, approval, and sandbox-binding state. Server checkpoints use a MySQL adapter implementing the supported store contract.

Recovery rules:

1. Restore queued messages, paused scheduling, and pending approvals.
2. Continue from the latest valid settled checkpoint without replaying already recorded tool effects.
3. An interrupted model request may be retried from that boundary and may incur additional provider cost.
4. A mutating operation or command that started without a confirmed receipt becomes `outcome_unknown`; pause for inspection and an explicit user decision. Never blindly re-run it.
5. A recorded effect without a complete model-facing result must be reconciled; its effect ledger alone is not proof that the framework can safely continue the pending tool batch.

Checkpoint snapshots are not filesystem snapshots. External filesystem effects and MySQL/local writes are not one atomic transaction. Neither StepPersistence nor execution receipts establish universal exactly-once execution. Do not introduce a durable workflow engine merely to store conversations.

## Events, logs, and diff

Approvals, execution receipts, checkpoints, recovery, steering, and compaction require structured traceable records plus readable console output. Correlate session/run/tool-call/approval/checkpoint identities. Show saved/restored boundary, operation state, decision source, duration, and safe result summaries. Do not log credentials.

Persist server-visible application events before publishing Redis hints or serving SSE. Support ordered replay and reconnect cursors. The browser derives state from snapshots and committed events rather than process-local drafts.

Diff is a presentation artifact, not an independent durable data requirement:

- Use framework edit events for live single-edit presentation.
- Compute approval previews from pending edit arguments and current content; revalidate on approval.
- Compute current workspace Git differences on demand, including staged/unstaged changes and separate handling of untracked files.
- Label workspace differences accurately: local pre-existing or concurrent user changes are not all attributable to the agent.
- Do not add a separate historical diff store or promise historical per-edit replay.
- Framework snapshots or pending arguments may inherently contain source text; this is distinct from intentionally duplicating a derived diff in application event storage.

Proposed UI: session list, chat stream, Queue/Steer selector, Stop/Continue, approval cards, execution trace, and on-demand changed-file/diff view. Proposed CLI: interactive input during execution, minimal controls for queue/steer/stop/continue, approval prompts, and a resume option. No large slash-command system.

## Context management

Include context compaction in release one. Prefer official capabilities and a configurable pre-request threshold. Keep recent turns and valid tool-call/result relationships; summarize older context. Retain original conversation records, save the effective post-compaction context for recovery, and log triggering reason plus before/after size or available usage information. Do not claim exact token counts if only estimates are available.

## Skills, MCP, and repository instructions

Use native Skills discovery and progressive loading, official MCP configuration/toolsets, and RepoContext. Disable sub-agent delegation.

User-managed configuration is trusted. Repository-provided configuration must be discovered without automatically activating it; expose it only after explicit trust approval. Trust is separate from tool-execution approval. Record content identity and invalidate trust when relevant trusted configuration changes. Skills support files affect behavior too; define the package-content trust scope rather than hashing only SKILL.md and implying bundled scripts are immutable.

Prefer reusable public trust components when available. Official CLAI has repository MCP trust UX, but that does not imply the framework loaders have a public equivalent. Skills exposure filters are not filesystem access controls. Repository instructions and trusted skills cannot change application permissions.

Support stdio and Streamable HTTP MCP. Stdio programs execute in the corresponding sandbox. Remote HTTP connections originate from the agent service and have separately configured destinations; an offline tool sandbox does not imply that remote MCP services are isolated or offline. Apply policy, approvals, receipts, and logging to MCP tools; do not infer authorization solely from tool annotations. No OAuth setup UI, MCP marketplace, or configuration editor is required. Include a small deterministic MCP example for demonstrations and integration tests.

## Test and delivery requirements

Run meaningful unit and integration tests, not merely mocks of the implementation. Include:

- Policy decisions, exact approval binding, explicit denials, stale edits, and stale approvals.
- Queue FIFO, steer-at-boundary, steering during approval, Stop/Continue, duplicate requests, and control races.
- Actual framework model/tool loops with deterministic test models and real Docker execution.
- Local bind-mount edits affecting the actual test workspace, with containment and network checks.
- Independent server session workspaces and configurable cross-session concurrency.
- MySQL persistence, Redis notification loss, SSE reconnect/replay, and browser refresh.
- Process restart at approval, settled checkpoint, and uncertain execution boundaries.
- Sandbox stop/restart, container recreation with retained volume, and cleanup reconciliation.
- Context compaction with valid tool protocol and recovered effective context.
- Skills trust/loading, repository instructions, and both MCP transports with policy enforcement.
- Frontend interaction integration tests and independent service rebuild/restart checks.

Run a bounded real DeepSeek smoke using the API key and base URL configured in `~/.zshrc`. Read only supported literal assignments without executing the shell file or printing secrets. Keep credentials outside Git. Document actual versions, commands, results, skipped checks, and material limitations. Do not claim checks passed when unavailable.

## Review and implementation sequence

1. Owner reviews this specification; no feature implementation before approval.
2. Verify and pin framework versions; probe DockerSandbox, StepPersistence, deferred approvals/steering, compaction, Skills, RepoContext, and MCP transports. Record reuse boundaries and any incompatibilities.
3. Implement the minimal local runtime and CLI with native persistence and learning logs.
4. Implement server persistence/scheduling, independent services, per-session sandboxes, and the web interface.
5. Complete unit, integration, container, browser, restart, and live-provider checks; document learning paths and known limits.

The existing sibling repositories are architectural references only. Favor the smallest readable implementation satisfying the confirmed semantics.

## Learning documents

- [Architecture](architecture.md)
- [Decisions](decisions.md)
- [CLI agent loop](cli-agent-loop.md)
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
