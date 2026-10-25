# Architecture

Status: planned. The [specification](specification.md) defines requirements; the [status page](implementation-status.md) lists implementation evidence.

## Service boundaries

![Planned service architecture](diagrams/system-architecture.png)

The browser talks to the API server. The API stores user intent and serves committed state. The agent server claims work from MySQL, runs the agent, and records results. Redis sends hints after database commits. A missed hint changes latency, not correctness.

| Component | Owns | Must not do |
| --- | --- | --- |
| Frontend | Chat, session list, controls, approval and trace display | Connect to MySQL, Docker, or the model |
| API server | Request validation, application transactions, snapshots, SSE | Execute tools or run the model loop |
| Agent scheduler | Session ordering, run ownership, recovery | Put business rules in framework tools |
| Agent runtime | Pydantic Agent and selected capabilities | Own session HTTP routes or database schema |
| Sandbox manager | Container and volume lifecycle | Give Docker control access to agent tools |
| Storage adapters | Framework and application persistence | Treat Redis as durable task storage |

The scheduler and sandbox manager belong to the agent-service application layer. They are not part of the model loop. This keeps business rules outside the runtime without requiring an extra service for every component.

## One web turn

1. The browser submits a message with a stable request identity and queue or steer mode.
2. The API commits the message and its scheduling change together.
3. The agent server claims eligible work. Only one run can be active in a session.
4. The runtime requests the model and executes approved tools in the session sandbox.
5. The agent server commits events, receipts, and checkpoint references at the required boundaries.
6. The API replays committed events over SSE. The browser reconnects with its last cursor.

A Redis hint may wake a reader after step 2 or step 5. Readers still query MySQL. The frontend must not depend on the original API process remaining alive.

## Data relationships

These are logical records, not a final SQL schema:

```text
Session
  +-- Messages and queued or steer input
  +-- Runs
  |    +-- Approval requests and decisions
  |    +-- Tool effects and receipts
  |    +-- Checkpoint references
  |    +-- Ordered display events
  +-- Sandbox binding -> container reference + workspace volume
```

Keep a user message and its scheduling change in one transaction. Check run ownership before committing execution state. Bind approval decisions to the pending call and reject expired versions. Save checkpoint references and their boundary events consistently. None of these transactions includes an external file or command effect.

## Local path

The CLI runs the same runtime in its own process. It uses a framework local store instead of MySQL and mounts the selected real repository into Docker. It does not require the web services or Redis. CLI input and rendering must remain responsive while the run executes.

## Proposed source layout

These directories do not exist yet. Names can change after framework API verification.

```text
src/pydantic_lab/
  cli/             terminal input and rendering
  api/             HTTP routes and SSE
  application/     sessions, controls, scheduling, recovery
  runtime/         agent construction and capability adapters
  storage/         local control state and MySQL adapters
  sandbox/         Docker lifecycle and workspace binding
frontend/          browser interface
examples/          sample skills and MCP service
tests/             unit and integration tests
docs/              specification and learning guides
```

Dependencies go from interfaces to application services, then to runtime and storage contracts. Keep modules small enough to read. Do not build an unrelated cross-framework abstraction.

## Deployment

Use separate Compose services and images for frontend, API, and agent server. Keep database data and session workspace volumes outside service images. Rebuild only the changed service. Schema migrations must remain compatible with a running agent service during frontend/API updates.

Only frontend/API ports bind to the host loopback address. MySQL, Redis, and agent-service interfaces stay internal. The trusted sandbox manager needs Docker control access. Tool containers must never receive that access. This is a local learning deployment, not a hostile multi-tenant platform.
