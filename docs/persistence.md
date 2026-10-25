# Persistence, Recovery, and Logs

Status: planned. Upstream documents the framework behavior. This lab does not yet have a storage adapter that has been tested.

## Three kinds of state

| State | Local CLI | Server |
| --- | --- | --- |
| Framework snapshots and tool effects | Native persistent StepStore | MySQL StepStore adapter |
| Sessions, controls, approvals, bindings | Small local application store where needed | MySQL application records |
| Workspace files | Real repository bind mount | Session volume |

StepPersistence saves message snapshots at settled steps and records events and tool effects. It does not store every application field, and it does not snapshot the workspace files. Choose a native local backend after the API probe. Reuse framework receipts where they already record the outcome. Do not store the same fact again under another name. See [Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/).

## Required recovery data

Keep the logical run identity, the schema and framework versions, the selected agent configuration, the latest valid checkpoint, pending approvals, control-message consumption, the scheduling pause, and the sandbox binding. Keep the original conversation records even when the model context has been compressed.

Store a policy revision and an extension configuration identity with the pending operation. If a configuration changes, reconcile the old approvals and bindings before continuing. A stable logical run can cover several framework continuation calls. Map the two identities explicitly.

## Restart rules

| Last known state | Required action |
| --- | --- |
| Queued | Restore order and scheduling pause |
| Awaiting approval, operation not started | Restore the pending request unless invalidated |
| Settled checkpoint with complete results | Continue from that boundary |
| Model request interrupted | Retry from the saved boundary; another provider charge is possible |
| Effect completed, model-facing result missing | Reconcile the result before continuation |
| Mutation or command started, outcome missing | Mark `outcome_unknown`, pause, and offer Continue without retry, Retry once, or Abort |

A database transaction cannot commit a shell effect and its receipt together. The process can exit after it changes a file and before it records completion. Returning to an older checkpoint does not undo that file change. Inspect an uncertain operation before choosing to retry or continue.

Stop an old execution attempt from writing after ownership has moved. Release one runs a single agent-service instance. Restart recovery still needs an ownership check, and proof that the previous commands cannot keep running unnoticed. There is no automatic exactly-once guarantee.

## Learning logs

Use structured records and readable console output. Correlate the session, logical run, framework run, tool call, approval, and checkpoint IDs. Include the time, event kind, state, decision source, and duration when they apply.

These are proposed application log labels:

```text
approval.requested   tool=edit_file
approval.decided     decision=allow_once
execution.started    tool_call_id=call_42
execution.completed  status=succeeded
checkpoint.saved     boundary=settled_step
checkpoint.loaded    reason=resume
```

Log queue acceptance, steer consumption, expired approvals, Stop, Continue, sandbox lifecycle, trust changes, and compaction. Keep credentials out of logs. Large command output may need truncation. When the displayed summary is incomplete, say so.

## Browser replay and diff

Commit server display events before publishing Redis hints. Give each event an ordered cursor. Commit coalesced assistant chunks before SSE delivery, so replay can reconstruct a partial answer. Flush on a closed Markdown block, 2 KiB, or a 100 ms buffer age, whichever comes first. Flush pending text before terminal and approval/tool boundary events. On reconnect, read from MySQL after that cursor. A snapshot plus replay must not leave a gap. The exact cursor scope and endpoint contract will be fixed when the implementation tests are written.

When the user asks, compute the current diff from Git and the workspace files. Include staged and unstaged changes, and list untracked files separately. A local diff can include edits the user made before the run or during it. Do not label every such change as the agent's work.

Do not add a separate store of historical diffs. Pending edit arguments and native snapshots can contain file text. If a framework event already contains diff data, keep that data for the framework's recovery contract. Leave the extra copy out of application display records.
