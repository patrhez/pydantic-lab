# Architecture

Status: implemented service boundaries. See [implementation status](implementation-status.md) for verified behavior and limits.

## Service boundaries

![Planned service architecture](diagrams/system-architecture.png)

The browser talks to the API server. The API stores user intent and serves state that has been committed. The agent server claims work from MySQL, runs the agent, and records the results. Redis sends a hint after the database commit. A missed hint only adds delay. The stored result stays the same.

| Component | Owns | Must not do |
| --- | --- | --- |
| Frontend | Chat, session list, controls, approval and trace display | Connect to MySQL, Docker, or the model |
| API server | Request validation, application transactions, snapshots, SSE | Execute tools or run the model loop |
| Agent scheduler | Session ordering, run ownership, recovery | Put business rules in framework tools |
| Agent runtime | Pydantic Agent and selected capabilities | Own session HTTP routes or database schema |
| Sandbox manager | Container and volume lifecycle | Give Docker control access to agent tools |
| Storage adapters | Framework and application persistence | Treat Redis as durable task storage |

The scheduler and the sandbox manager belong to the agent-service application layer. They are not part of the model loop. Business rules stay outside the runtime, and each of these roles does not need its own service.

## One web turn

1. The browser submits a message with a stable request identity and a queue or steer mode.
2. The API commits the message and its scheduling change in one transaction.
3. The agent server claims work that is eligible to run. A session can have only one active run.
4. The runtime requests the model and runs approved tools in the session sandbox.
5. The agent server commits events, receipts, and checkpoint references at the required boundaries.
6. The API replays committed events over SSE. The browser reconnects from its last cursor.

Redis publishes a hint after step 2 or step 5. This release uses bounded polling and queries MySQL directly. The frontend must keep working if the original API process is gone.

Read-only diff, approval preview, and extension inspection pass through the API to an internal agent-service endpoint. Their derived content is transient. Lifecycle actions use durable commands.

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

Keep a user message and its scheduling change in one transaction. Check run ownership before committing execution state. Bind an approval decision to the pending call, and reject a decision for an invalidated request or changed policy/configuration revision. Native snapshots commit before their boundary log. Recovery reads the native store if that log is missing. None of these transactions includes an external file change or command effect.

## Local path

The CLI runs the same runtime in its own process. It uses a framework local store instead of MySQL, and it mounts the selected real repository into Docker. It does not need the web services or Redis. CLI input and rendering must stay responsive while the run executes.

## Source layout

These directories contain the implementation. See the [source map](implementation.md#source-map).

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

Dependencies point from interfaces to application services, then to runtime and storage contracts. Keep modules small enough to read. Do not build an unrelated cross-framework abstraction.

## Deployment

Use separate Compose services and images for the frontend, the API, and the agent server. Keep database data and session workspace volumes outside the service images. Rebuild only the service that changed. Schema migrations must stay compatible with an agent service that is still running while the frontend or API is updated.

Only frontend and API ports bind to the host loopback address. MySQL, Redis, and the agent-service interfaces stay internal. The trusted sandbox manager needs Docker control access. Tool containers must never receive that access. This is a local learning deployment, not a multi-tenant platform.
