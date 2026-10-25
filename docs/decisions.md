# Design Decisions

Status: agreed choices implemented with pinned public framework APIs. See [implementation details](implementation.md) for the adapters and their costs.

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| One standalone lab with two interfaces | Compare the same behavior without sibling shared packages | Interface adapters still need separate tests |
| Use public framework features first | Learn Pydantic AI rather than a replacement loop | Pin versions and verify extension points |
| Separate API and agent deployments | UI and API changes must not stop execution | Requires durable coordination |
| Use MySQL as server truth | Preserve sessions, controls, and checkpoints across restart | Requires transactions and a store adapter |
| Use Redis for hints only | Lost notifications must not lose work | Readers need polling or replay fallback |
| Commit bounded assistant chunks before SSE | A 100 ms maximum buffer age keeps short output visible; boundary flushes preserve replay | More database writes than transient token deltas |
| Use DockerSandbox in both modes | Keep file and command execution consistent | Commands use Linux tools |
| Bind-mount the local repository | Let users inspect and edit the same files | Approved tools can damage mounted files |
| Give each server session a volume | Keep sessions independent and files persistent | Requires cleanup and resource limits |
| Clone public Git repositories | Provide a clear server workspace source | Private credentials and pushing are out of scope |
| Stop idle containers, keep volumes | Reduce idle resource use | Processes and stdio connections must restart |
| Keep setup approval available during provisioning | Initialization commands follow the execution policy | Chat waits until setup finishes |
| Preserve focus when approval arrives | Typing and Enter must not accidentally approve an operation | Users explicitly open approval review |
| Require Stop before deleting an active session | Avoid deletion races with tool execution | Users need an extra step before cleanup |
| Change sandbox networking only between runs | Apply and verify Docker state before the next operation | Users cannot toggle it during execution |
| Default to offline execution | Make network access explicit | Install dependencies during controlled setup |
| Use one agent, no delegates | Focus on execution and recovery | No parallel sub-agent research |
| Serialize runs per session | Prevent conflicting workspace writes | A pending approval blocks queued runs |
| Queue by default during an active run | Make ordinary follow-ups predictable | Steer requires an explicit mode change |
| Inject steer at a safe boundary | Change direction without replacing the logical run | A running tool finishes first |
| Invalidate pending approvals on steer | Old plans must not execute after a new instruction | The pending tool protocol needs explicit resolution |
| Stop cancels and pauses the queue | Stop must not immediately launch another run | Users must select Continue |
| First Ctrl+C sends Stop | Match terminal expectations without bypassing durable control state | Process exit needs a second press |
| Default mutations to approval | Expose execution decisions for learning | More prompts unless users configure auto-allow rules |
| Keep approvals pending without time expiry | Restart-safe decisions must not disappear because time passed | Old prompts need explicit invalidation and clear labels |
| Reuse native checkpoint storage | Avoid a second recovery engine | Application controls still need persistence |
| Pause unknown effects | Avoid repeating an external effect with an unknown result | Users may need to inspect the workspace |
| Offer Continue without retry, Retry once, or Abort after inspection | Cover observed success, explicit retry, and cancellation without hidden retries | Continue without retry uses a manually reconciled model-facing result |
| Compute diff on demand | Current changes come from files and Git | No historical per-edit diff replay |
| Compact model context, keep records | Limit context without deleting conversation evidence | Summaries may omit detail |
| Trust repository extensions explicitly | A repository must not activate its own programs | Configuration changes can require new approval |
| Make trust durable per category and content | Avoid repeated prompts for unchanged repository content | Trust storage and content identity become required |
| Support stdio and HTTP MCP | Cover local programs and independent services | Two transport lifecycles require tests |
| Single local user | Keep scope on agent execution | No remote-user access controls |
| Support plain one-shot CLI output | Keep pipes and CI logs useful | Approval requires a saved state, resume instruction, and exit status 3 |
| Resume the latest CLI session by default | Make common recovery fast | Multiple recoverable sessions require an explicit ID |
| Use a modern developer console visual direction | Keep dense execution state readable and attractive | Requires consistent tokens and component states |

## Technology defaults awaiting verification

Use Python with uv, FastAPI, React/TypeScript with Vite, and Docker Compose. Select compatible Pydantic AI and Harness versions after executable probes. Use a framework local file or SQLite backend. Do not design a custom local checkpoint schema first.

## How decisions change

Update this record and the specification together. State what changed and what that change affects. Leave abandoned experiments out of the main guides unless they explain a current limit.
