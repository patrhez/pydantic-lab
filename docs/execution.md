# Agent Execution and User Controls

Status: planned. Proposed state names and log labels below are application examples, not framework event names.

![Planned execution boundaries](diagrams/execution.png)

## Framework loop and application controls

Pydantic AI owns model requests, tool dispatch, and output validation. The application owns user intent, permission decisions, persistence, and execution ownership. A checkpoint hook does not replace these application controls.

Before each model request, the controller checks Stop, restores any required protocol state, consumes eligible steer input, and applies context management. It then lets the framework continue. Persist steer consumption with its recovery state so a restart cannot inject the same message twice.

A safe boundary must have a valid message history. Do not insert a new user message between a tool call and its required result. For a tool batch, settle all started calls and resolve unexecuted calls before the next model request. Verify the exact public hooks with the pinned version.

## Queue, steer, and Stop

| Input | Active run | Queued input |
| --- | --- | --- |
| Queue | Continue unchanged | Append a new turn in FIFO order |
| Steer | Inject before the next model request | Keep existing queued turns |
| Steer while awaiting approval | Expire pending approvals and re-plan in the same logical run | Keep existing queued turns |
| Stop | Cancel; try to stop active commands | Preserve input and pause scheduling |
| Continue | Do not revive a cancelled run | Resume eligible queued turns |

The scheduler is separate from a run. A stopped run remains cancelled even after Continue. A run awaiting approval occupies its session execution slot, but it need not occupy a scarce model-request permit or keep an idle container running.

For a steer during approval, record invalidation before accepting further decisions. Complete the framework's pending-tool protocol without executing the old plan. Do not silently turn steer into cancel-and-start-new-run. A stale approval response must have no effect.

## Permission path

1. Validate workspace restrictions and explicit denials.
2. Match a trusted auto-allow rule, if one exists.
3. Otherwise create a pending approval for mutations and commands.
4. Bind the decision to the exact call, arguments, and policy revision.
5. After approval, recheck the target and record execution start before invoking the tool.
6. Record the known outcome and return the tool result to the framework.

Allow Once applies to one request. Reject Once returns a refusal to the agent. Approval does not bypass a denied path, a denied command, or a content conflict. MCP tools follow the same policy path; remote tool metadata alone cannot grant permission.

The official Shell command filter checks executable names and selected operators. It is not a full shell authorization engine. Docker remains the isolation boundary. See [Shell command controls](https://pydantic.dev/docs/ai/harness/shell/#command-controls).

## File events

The official FileSystem capability emits `FileChangeRequestEvent` before a change with immediate dispatch. Listeners finish before execution continues. After a successful edit, `FileEditedEvent` enters the run event stream. Stream listeners run in order; this is not a separate consumer thread by definition.

Use the request for preview and veto behavior where appropriate. Use the completion event for display. Durable human approval must also survive a process exit, so a waiting event callback alone is insufficient. Do not use a completion notification as proof that MySQL and the filesystem committed atomically. See [FileSystem events](https://pydantic.dev/docs/ai/harness/filesystem/#events).

## Display and ordering

Preserve committed partial assistant output when a run stops. Mark it as stopped; do not treat it as a completed assistant answer in later model context. Keep completed tool results available for recovery. Show pending queue items, steer acceptance, approval state, and scheduling pause separately.

API requests use stable client identities. Duplicate submissions return the existing result. They must not apply Stop or steer twice. Transaction and locking details must be tested before this design is marked implemented.
