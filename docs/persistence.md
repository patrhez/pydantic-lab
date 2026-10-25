# Persistence, Recovery, and Logs

Status: planned. Framework behavior is documented upstream; this lab has no tested storage adapter yet.

## Three kinds of state

| State | Local CLI | Server |
| --- | --- | --- |
| Framework snapshots and tool effects | Native persistent StepStore | MySQL StepStore adapter |
| Sessions, controls, approvals, bindings | Small local application store where needed | MySQL application records |
| Workspace files | Real repository bind mount | Session volume |

StepPersistence saves message snapshots at settled steps and records events and tool effects. It does not capture every application field or the workspace filesystem. Select a native local backend after the API probe. Reuse framework receipts where possible rather than duplicating their meaning. See [Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/).

## Required recovery data

Keep the logical run identity, schema and framework versions, selected agent configuration, latest valid checkpoint, pending approvals, control-message consumption, scheduling pause, and sandbox binding. Preserve original conversation records independently of compressed model context.

Keep a policy revision and extension configuration identity with the pending operation. If a configuration changes, reconcile old approvals and bindings before continuation. A stable logical run may span framework continuation calls; map both identities explicitly.

## Restart rules

| Last known state | Required action |
| --- | --- |
| Queued | Restore order and scheduling pause |
| Awaiting approval, operation not started | Restore the pending request unless invalidated |
| Settled checkpoint with complete results | Continue from that boundary |
| Model request interrupted | Retry from the saved boundary; another provider charge is possible |
| Effect completed, model-facing result missing | Reconcile the result before continuation |
| Mutation or command started, outcome missing | Mark `outcome_unknown` and pause |

A database transaction cannot commit a shell effect and its receipt together. A process can die after changing a file and before recording completion. Returning to an older checkpoint does not undo that file change. Inspect uncertain operations before deciding to retry or continue.

Prevent old execution attempts from writing after ownership changes. Release one runs one agent-service instance; restart recovery still requires an ownership check and proof that previous commands cannot continue unnoticed. No automatic exactly-once guarantee is made.

## Learning logs

Use structured records and readable console output. Correlate session, logical run, framework run, tool call, approval, and checkpoint IDs. Include time, event kind, state, decision source, and duration where applicable.

These are proposed application log labels:

```text
approval.requested   tool=edit_file
approval.decided     decision=allow_once
execution.started    tool_call_id=call_42
execution.completed  status=succeeded
checkpoint.saved     boundary=settled_step
checkpoint.loaded    reason=resume
```

Log queue acceptance, steer consumption, expired approvals, Stop, Continue, sandbox lifecycle, trust changes, and compaction. Keep credentials out of logs. Large command output may need truncation; the displayed summary must say when output is incomplete.

## Browser replay and diff

Commit server display events before publishing Redis hints. Give events an ordered cursor. Reconnection reads from MySQL after that cursor; a snapshot and replay must not leave a gap. The exact cursor scope and endpoint contract will be defined with implementation tests.

Compute current diff from Git and workspace files when requested. Include staged and unstaged changes and list untracked files separately. A local diff can include user changes made before or during the run. Do not label all such changes as agent-authored.

Do not add a separate historical diff store. Pending edit arguments and native snapshots can contain file text. If framework events contain diff data, keep the original framework recovery contract intact while omitting unnecessary diff copies from application display records.
