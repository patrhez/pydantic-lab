# Framework Integrations

Status: proposed integration plan. Public documentation was reviewed on 2026-10-25. No package version or integration probe has been verified in this repository.

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

Framework symbols can change. Pin versions, run small probes, and document the actual hooks before building adapters. Do not replace a missing hook with private CLAI imports.

## Skills and repository instructions

Skills discovers packages, exposes a catalog, and loads instructions when needed. `include` and `exclude` select catalog entries. They do not enforce file permissions. A trusted skill's script still runs through approved sandbox tools. See [Skills](https://pydantic.dev/docs/ai/harness/skills/).

RepoContext supplies repository instructions. Load the configured applicable files only after trust approval. Log which files were loaded. Do not promise nested instruction scope until verified with the selected version. See [Repo Context](https://pydantic.dev/docs/ai/harness/repo-context/).

User-managed configuration is trusted. Discover repository configuration without activating it. Record trust against content identity. Include relevant skill support files in the trust scope. Recheck changes before later use; the repository cannot approve its own changes.

Official CLAI includes an MCP trust workflow. That is an application feature, not proof of a reusable public loader API. If no public component fits, add a small trust adapter. Configuration trust and execution approval remain separate.

## MCP transports

Use the official [MCP client](https://pydantic.dev/docs/ai/mcp/client/) and loader for trusted definitions.

- **stdio:** run the program inside the session sandbox. A proposed transport launches `docker exec -i` with explicit arguments. Verify process cleanup and transport errors. The Docker bridge runs in the trusted controller, not as an agent tool.
- **Streamable HTTP:** connect from the agent service to a configured destination. Configure credentials through environment references. Do not put secrets in repository files.

Apply approval and receipt rules to MCP tools. Tool annotations are hints, not authority. Include a deterministic example service and tests for both transports. OAuth setup, configuration editing UI, and a marketplace are out of scope.

## Compaction

Choose an official capability that works with the configured DeepSeek model. Do not assume provider-native compaction support. Trigger compaction before a request reaches the configured context budget. Keep recent turns and valid tool protocol pairs. Preserve the original records and persist the compacted model context for recovery. See [Compaction](https://pydantic.dev/docs/ai/harness/compaction/).

## Required probes

Prove Docker volume binding and reattachment, native snapshot continuation, deferred approval persistence, steer during approval, context compaction, trust-filtered loading, and both MCP transports. Record versions, commands, and results in the status page. Escalate a requirement conflict instead of silently changing its meaning.
