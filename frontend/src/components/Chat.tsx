import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Check,
  ChevronDown,
  Layers,
  ShieldCheck,
  Square,
  Terminal,
} from "lucide-react";
import { Approval, Run, label } from "../types";
import { Status } from "./Status";
function Markdown({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>;
}
export function ApprovalCard({
  approval,
  onDecide,
  onReview,
}: {
  approval: Approval;
  onDecide: (a: Approval, allow: boolean) => void;
  onReview?: () => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const pending = approval.status === "pending";
  const [submitting, setSubmitting] = useState(false);
  const choose = async (allow: boolean) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onDecide(approval, allow);
    } finally {
      setSubmitting(false);
    }
  };
  if (!pending)
    return (
      <details className="settled-approval">
        <summary>
          <ShieldCheck size={13} />
          <span>
            {label(approval.status)} · {approval.tool}
          </span>
          <span className="mono">{approval.id.slice(0, 8)}</span>
        </summary>
        <p className="small muted">{approval.reason}</p>
        <pre>{JSON.stringify(approval.arguments, null, 2)}</pre>
      </details>
    );
  return (
    <section
      id={"approval-" + approval.id}
      tabIndex={-1}
      className={"approval-card " + (!pending ? "settled" : "")}
      aria-label={"Approval for " + approval.tool}
    >
      <div className="eyebrow amber">
        <ShieldCheck size={13} />{" "}
        {pending ? "APPROVAL REQUIRED" : approval.status.toUpperCase()}{" "}
        <span className="mono">{approval.id.slice(0, 8)}</span>
      </div>
      <h3>
        {pending ? "Allow this exact operation?" : label(approval.status)}
      </h3>
      <div className="muted mono small">
        {approval.tool} ·{" "}
        {String(
          approval.arguments.path || approval.arguments.command || "Tool call",
        )}
      </div>
      <pre>{JSON.stringify(approval.arguments, null, 2)}</pre>
      {pending && ["write_file", "edit_file"].includes(approval.tool) && (
        <div>
          <button
            onClick={async () => {
              try {
                const sid = location.pathname.split("/sessions/")[1];
                const response = await fetch(
                  `/api/sessions/${sid}/workspace/approval?approval_id=${approval.id}`,
                );
                const data = await response.json();
                setPreview(response.ok ? data.diff : data.detail);
              } catch {
                setPreview("Preview unavailable. Retry inspection.");
              }
            }}
          >
            Preview proposed diff
          </button>
          {preview !== null && (
            <pre className="diff-code">{preview || "No content change"}</pre>
          )}
        </div>
      )}
      {pending ? (
        <div className="button-row">
          <button
            className="primary"
            disabled={submitting}
            onClick={() => choose(true)}
          >
            {submitting ? "Submitting…" : "Allow Once"}
          </button>
          <button disabled={submitting} onClick={() => choose(false)}>
            Reject Once
          </button>
        </div>
      ) : (
        <p className="muted small">{approval.reason}</p>
      )}
      <p className="small muted">
        Approval applies to this operation. Targets and policy are checked again
        before execution.
      </p>
    </section>
  );
}
export function RunView({
  run,
  onDecide,
}: {
  run: Run;
  onDecide: (a: Approval, b: boolean) => void;
}) {
  return (
    <article className="run-block">
      <div className="user-message">
        <div className="message-avatar">Y</div>
        <div>
          <div className="message-label">
            YOU <span>{run.status === "queued" ? "QUEUED" : ""}</span>
          </div>
          <p>{run.prompt}</p>
        </div>
      </div>
      {run.steers.map((s) => (
        <div key={s.id} className="steer-message">
          <span className="eyebrow">
            STEER {s.consumed ? "CONSUMED" : "RECORDED"}
          </span>
          <p>{s.content}</p>
        </div>
      ))}
      {(run.answer || run.status === "running") && (
        <div className="assistant-message">
          <div className="agent-avatar">
            <Layers size={17} />
          </div>
          <div className="answer-body">
            <div className="message-label">
              PYDANTIC AGENT <Status value={run.status} />
            </div>
            {run.answer ? (
              <div className="markdown">
                <Markdown>{run.answer}</Markdown>
              </div>
            ) : (
              <div className="thinking">
                <span />
                <span />
                <span />
                Working in the sandbox
              </div>
            )}
          </div>
        </div>
      )}
      {Object.values(run.receipts).length > 0 && (
        <details className="tool-summary">
          <summary>
            <Terminal size={14} />
            {Object.keys(run.receipts).length} tool operation
            {Object.keys(run.receipts).length > 1 ? "s" : ""}
            <ChevronDown size={13} />
          </summary>
          {Object.values(run.receipts).map((r) => (
            <div className="tool-line" key={r.call_id}>
              <span className="mono">{r.tool}</span>
              <Status value={r.status} />
            </div>
          ))}
        </details>
      )}
      {run.approvals.map((a) => (
        <ApprovalCard key={a.id} approval={a} onDecide={onDecide} />
      ))}
      {run.error && <div className="error-banner">{run.error}</div>}
      {run.status === "cancelled" && (
        <div className="stopped-marker">
          <Square size={11} />
          Stopped · partial output retained
        </div>
      )}
      {run.native_ids.length > 0 && (
        <div className="checkpoint-line">
          <Check size={12} />
          {run.native_ids.length} framework segment
          {run.native_ids.length > 1 ? "s" : ""} · checkpoint records available
        </div>
      )}
    </article>
  );
}
