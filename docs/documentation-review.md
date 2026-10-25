# Documentation Review

Review date: 2026-10-25. Scope: documentation and editable diagrams only. Wording was revised the same day. Requirements were left unchanged.

## Result

The guides cover the confirmed product decisions. The manual review found no unresolved requirement conflict. Runtime behavior still needs executable checks, including framework APIs, recovery hooks, and the proposed service layout.

The repository has no application code. The README and the status page say so. Examples of application log labels and source directories are marked as proposals.

## Requirement coverage

| Specification area | Learning document | Required verification |
| --- | --- | --- |
| Two interfaces and service boundaries | [Architecture](architecture.md) | Independent service updates |
| MySQL truth and Redis hints | [Architecture](architecture.md), [Persistence](persistence.md) | Lost hints and SSE replay |
| Local bind mount and server session volumes | [Sandboxes](sandboxes.md) | Actual file changes and session isolation |
| Container lifecycle and network | [Sandboxes](sandboxes.md) | Restart, replacement, and network change |
| Queue, steer, Stop, and Continue | [Execution](execution.md) | Ordering, pause, and control races |
| CLI loop components and failure positions | [CLI agent loop](cli-agent-loop.md) | Framework continuation and effect recovery |
| Approval and allowlists | [Execution](execution.md) | Exact-call binding and stale decisions |
| Checkpoints, receipts, and unknown effects | [Persistence](persistence.md) | Process failure at execution boundaries |
| Learning logs and derived diff | [Persistence](persistence.md) | Correlation fields and current workspace diff |
| Compaction | [Integrations](integrations.md) | Valid tool protocol and restart |
| Skills, MCP, and repository instructions | [Integrations](integrations.md) | Trust changes and both transports |
| Single user and single agent | [Decisions](decisions.md) | Configuration and deployment checks |
| Tests and live DeepSeek smoke | [Verification](verification.md) | Recorded commands and results |
| English and commit conventions | [Contribution rules](../CONTRIBUTING.md) | Review each change |

## Corrections made

- Stopping a container also ends stdio MCP processes and connections.
- Report an updated network permission only after the Docker network has actually changed.
- Continue resumes queued work. It does not restart a cancelled run.
- Queued messages stay in place when steer changes the active run.
- Stopped display text is separate from a completed assistant message in model context.
- Native framework event storage is separate from extra application copies of a derived diff.
- Package versions, public-hook selection, source layout, and protocols are still unverified.
- A status page records evidence, so a design guide cannot stand in for an implementation.

These points record the agreed behavior. Feature implementation still waits for specification approval.

## Writing

The guides use direct technical English: active voice, the terms in the index, and a short sentence when a short sentence is clearer. Promotional language and invented names are left out. ASD-STE100 is a readability aim, not a certified word list. This page is not a compliance score.

## Diagram review

All three Excalidraw sources were rendered with the official Excalidraw library and checked as PNG images. The architecture heading was moved so it no longer crosses connector lines. The Redis-to-API hint path was added. The CLI diagram was added to show model calls, dispatch, HITL, permission checks, receipts, checkpoints, and recovery. Sources and previews describe the same design.

The installed skill renderer could not finish its CDN imports. A temporary local bundle of Excalidraw 0.18.0 and Playwright produced the previews. Those rendering tools stayed outside the repository. They are not agent runtime dependencies.

## Checks

Completed checks:

- Validated 16 Markdown files and 74 local links and anchors. After the wording pass, the same files, links, and heading anchors still resolve.
- Parsed three Excalidraw scenes and checked unique IDs and binding references.
- Rendered and visually inspected three PNG previews.
- Checked the earlier draft for non-ASCII text and for sentences over 35 words. That draft had neither issue. The later wording pass prefers a clear sentence over a fixed word cap.
- Compared guides against the specification and the requirement coverage table.

Check staged whitespace and the final file list immediately before commit. This change is documentation only. Runtime tests were not run, and they are not reported as passing.
