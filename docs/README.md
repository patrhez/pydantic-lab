# Documentation

These documents describe the system we plan to build. None of it has been implemented or tested. See the [implementation status](implementation-status.md) for what exists in the repository today.

## Reading order

| Document | Purpose |
| --- | --- |
| [Specification](specification.md) | Required behavior and release scope |
| [Decisions](decisions.md) | Reasons, alternatives, and costs |
| [Architecture](architecture.md) | Services, data ownership, and deployment |
| [CLI agent loop](cli-agent-loop.md) | Model calls, tools, HITL, receipts, and recovery positions |
| [Execution](execution.md) | Agent loop, approvals, queue, steer, and Stop |
| [Persistence and recovery](persistence.md) | Checkpoints, receipts, logs, and restart behavior |
| [Sandboxes](sandboxes.md) | Local mounts, session volumes, network, and lifecycle |
| [Framework integrations](integrations.md) | Native features and required adapters |
| [Verification](verification.md) | Unit, integration, browser, and live tests |
| [Implementation status](implementation-status.md) | Evidence and remaining work |
| [Documentation review](documentation-review.md) | Consistency checks and corrections |

## Diagrams

The [CLI agent-loop diagram](diagrams/cli-agent-loop.excalidraw) and its [preview](diagrams/cli-agent-loop.png) show where the terminal runtime components sit.

The [system architecture](diagrams/system-architecture.excalidraw) is editable in Excalidraw. Its [PNG preview](diagrams/system-architecture.png) is embedded in the architecture guide. The [execution diagram](diagrams/execution.excalidraw) and [preview](diagrams/execution.png) show the approval and recovery boundaries.

Diagram labels describe the design. They are not implemented HTTP routes or event schemas. See the [diagram notes](diagrams/README.md).

## Terms

| Term | Meaning |
| --- | --- |
| Session | A conversation, its controls, and its workspace binding |
| Run | One logical agent execution, including steer input |
| Tool call | One model-requested operation |
| Approval | Permission for one exact pending operation |
| Receipt | A durable record of an operation's known result |
| Checkpoint | A saved framework execution boundary |
| Sandbox | The isolated environment used by tools |
| Workspace | The files that tools can read or change |
| Event | A record used to reconstruct execution or display state |

A session is the conversation and its controls. The container is a separate sandbox resource. A checkpoint saves an execution boundary. It does not copy the workspace files. An event records state for recovery or display. Saving the event and committing the external operation plus its receipt are separate steps.
