# Documentation

These documents describe the planned system. No runtime behavior has been implemented or tested. Read the [implementation status](implementation-status.md) before using a guide as evidence.

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

The [CLI agent-loop diagram](diagrams/cli-agent-loop.excalidraw) and its [preview](diagrams/cli-agent-loop.png) locate the terminal runtime components.

The [system architecture](diagrams/system-architecture.excalidraw) is editable in Excalidraw. Its [PNG preview](diagrams/system-architecture.png) is embedded in the architecture guide. The [execution diagram](diagrams/execution.excalidraw) and [preview](diagrams/execution.png) show approval and recovery boundaries.

Diagram labels describe the design. They do not establish an implemented HTTP route or event schema. See the [diagram notes](diagrams/README.md).

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

A session is not a container. A checkpoint is not a file backup. An event is not proof that an external operation and its receipt committed together.
