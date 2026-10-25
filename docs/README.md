# Documentation

These documents describe the system we plan to build. None of it has been implemented or tested. See the [implementation status](implementation-status.md) for what exists in the repository today.

## Reading order

| Document | Purpose |
| --- | --- |
| [Specification](specification.md) | Required behavior and release scope |
| [Decisions](decisions.md) | Reasons, alternatives, and costs |
| [Architecture](architecture.md) | Services, data ownership, and deployment |
| [CLI agent loop](cli-agent-loop.md) | Model calls, tools, HITL, receipts, and recovery positions |
| [CLI interactions](cli-interactions.md) | Terminal layout, controls, approvals, resume, and acceptance criteria |
| [Web interactions](web-interactions.md) | Session UI, streaming, controls, recovery, and acceptance criteria |
| [Visual design](visual-design.md) | Design direction, tokens, components, terminology, and mockups |
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

The interaction mockups use editable SVG sources and rendered PNG previews: [CLI workspace](diagrams/cli-workspace.png), [Web workspace](diagrams/web-workspace.png), [Web key states](diagrams/web-key-states.png), and [run control state flow](diagrams/session-state-flow.png).

## Terms

| Term | Meaning |
| --- | --- |
| Session | A conversation, its controls, and its workspace binding |
| Run | One logical agent execution, including steer input |
| Queue | A FIFO follow-up that becomes a later run |
| Steer | Input injected into the current logical run at a safe boundary |
| Tool call | One model-requested operation |
| Approval | Permission for one exact pending operation |
| Receipt | A durable record of an operation's known result |
| Checkpoint | A saved framework execution boundary |
| Outcome unknown | A started operation without a confirmed result |
| Sandbox | The isolated environment used by tools |
| Workspace | The files that tools can read or change |
| Trust | Permission to load extension configuration content, separate from execution approval |
| Event | A record used to reconstruct execution or display state |

A session is the conversation and its controls. The container is a separate sandbox resource. A checkpoint saves an execution boundary. It does not copy the workspace files. An event records state for recovery or display. Saving the event and committing the external operation plus its receipt are separate steps.
