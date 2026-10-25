# Framework Integrations

Status: proposed integration plan. Public documentation was reviewed on 2026-10-25. This repository has not yet pinned a package version or run an integration probe.

## Reuse before adaptation

| Feature | Preferred public capability | What the lab must add |
| --- | --- | --- |
| Loop and typed tools | Pydantic AI Agent | Limits and injected application context |
| Files and commands | FileSystem and Shell | Policy routing and user presentation |
| Isolation | DockerSandbox | Session bindings and lifecycle |
| Checkpoints | StepPersistence and StepStore | MySQL adapter and recovery policy |
| Approval | Native deferred tools and results | Durable requests, decisions, and invalidation |
| Compaction | Official compaction capabilities | Threshold configuration and logs |
| Skills | Skills | Trusted source selection |
| Repository instructions | RepoContext | Trust gate and loaded-file records |
| MCP | MCPToolset and configuration loader | Transport placement and permission routing |

Framework symbols can change. Pin versions, run small probes, and record the actual hooks before building adapters. If a hook is missing, do not fill the gap with private CLAI imports.

Online documentation confirms these boundaries, subject to version probes:

- Deferred approvals use `DeferredToolRequests`, durable conversation state, and `DeferredToolResults`. A follow-up run has a new framework run ID. Correlate it to the logical application run.
- StepPersistence ships in-memory, file, SQLite, MongoDB, and PostgreSQL stores. MySQL requires a custom `StepStore` adapter.
- StepPersistence records snapshots and tool effects. Automatic execution recovery remains an application responsibility.
- No public trust component is documented for Skills, RepoContext, or MCP configuration. Add the narrow trust adapter allowed by the specification.
- Harness compaction strategies are model-agnostic. Provider-native compaction is documented for OpenAI and Anthropic, not for DeepSeek.
- DockerSandbox supports creation, reattachment, and destruction. Idle stop, named workspace volumes, and network-change reconciliation stay in the application layer.

## Skills and repository instructions

Skills discovers packages, exposes a catalog, and loads instructions when they are needed. `include` and `exclude` select catalog entries. They do not enforce file permissions. A trusted skill's script still runs through approved sandbox tools. See [Skills](https://pydantic.dev/docs/ai/harness/skills/).

RepoContext supplies repository instructions. Load the configured files that apply only after the user approves trust. Log which files were loaded. Do not state a nested instruction scope until the selected version confirms it. See [Repo Context](https://pydantic.dev/docs/ai/harness/repo-context/).

User-managed configuration is trusted. Discover repository configuration and leave it inactive. Record trust against the content identity. Include the relevant skill support files in the trust scope. Check for changes before later use. The repository cannot approve its own changes.

Official CLAI includes an MCP trust workflow. That workflow belongs to the CLAI application. It does not show that a public loader API does the same job. If no public component fits, add a small trust adapter. Trust in configuration and approval to execute stay separate decisions.

## MCP transports

Use the official [MCP client](https://pydantic.dev/docs/ai/mcp/client/) and loader for trusted definitions.

- **stdio:** run the program inside the session sandbox. A proposed transport launches `docker exec -i` with explicit arguments. Check process cleanup and transport errors. The Docker bridge runs in the trusted controller. It is not an agent tool.
- **Streamable HTTP:** connect from the agent service to a configured destination. Pass credentials through environment references. Do not put secrets in repository files.

Apply the approval and receipt rules to MCP tools. Tool annotations are hints, not authorization. Include a deterministic example service and tests for both transports. OAuth setup, a configuration editor, and a marketplace are out of scope.

## Compaction

Choose an official capability that works with the configured DeepSeek model. Do not assume the provider compacts context itself. Run compaction before a request reaches the configured context budget. Keep recent turns and valid tool-call/result pairs. Keep the original records, and persist the compacted model context for recovery. See [Compaction](https://pydantic.dev/docs/ai/harness/compaction/).

## Required probes

Prove Docker volume binding and reattachment, native snapshot continuation, deferred approval persistence, steer during approval, context compaction, trust-filtered loading, and both MCP transports. Record versions, commands, and results on the status page. If a probe conflicts with a requirement, raise that conflict. Do not quietly change what the requirement means.
