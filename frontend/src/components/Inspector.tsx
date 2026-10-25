import {
  Layers,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { Session, label } from "../types";
import { Status } from "./Status";
type Props = {
  session: Session;
  tab: string;
  setTab: (tab: string) => void;
  pendingActions: boolean | undefined;
  blocked: boolean;
  busy: boolean;
  refresh: (id: string) => Promise<unknown>;
  action: (kind: string, payload?: Record<string, unknown>) => Promise<void>;
  ask: (
    title: string,
    message: string,
    fn: () => Promise<void>,
    typed?: boolean,
  ) => void;
};
export function Inspector({
  session,
  tab,
  setTab,
  pendingActions,
  blocked,
  busy,
  refresh,
  action,
  ask,
}: Props) {
  return (
    <aside className="inspector">
      <div className="inspector-title">
        <span>
          <Settings2 size={15} />
          Inspector
        </span>
        <button
          className="icon-button"
          aria-label="Refresh session"
          onClick={() => refresh(session.id)}
        >
          <RefreshCw size={14} />
        </button>
      </div>
      <div className="inspector-tabs" role="tablist">
        {["Trace", "Diff", "Sandbox", "Extensions"].map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="inspector-body">
        {tab === "Trace" && (
          <>
            <div className="eyebrow">EXECUTION RECORDS</div>
            <h3>Every step, accounted for.</h3>
            <p className="muted small">
              Receipts and checkpoints make the execution boundary visible.
            </p>
            {session.runs
              .flatMap((r) => Object.values(r.receipts))
              .map((r, i) => (
                <details className="trace-item" key={i}>
                  <summary>
                    <Terminal size={14} />
                    <span>{r.tool}</span>
                    <Status value={r.status} />
                  </summary>
                  <pre>
                    {typeof r.result === "string"
                      ? r.result
                      : JSON.stringify(r.result, null, 2)}
                  </pre>
                  <div className="mono muted small">
                    {r.call_id} · {r.duration_ms ?? "–"} ms
                  </div>
                </details>
              ))}
            {!session.runs.some((r) => Object.keys(r.receipts).length) && (
              <div className="inspector-empty">
                <Layers size={26} />
                <p>No tool calls yet.</p>
                <span>Execution records will appear here.</span>
              </div>
            )}
            {session.records
              ?.filter((e) =>
                [
                  "checkpoint.saved",
                  "checkpoint.loaded",
                  "compaction.completed",
                  "steer.consumed",
                  "recovery.required",
                ].includes(e.kind),
              )
              .slice(-20)
              .map((e) => (
                <details className="trace-item" key={e.id}>
                  <summary>
                    <Layers size={13} />
                    <span>{label(e.kind.replace(".", " "))}</span>
                  </summary>
                  <pre>{JSON.stringify(e, null, 2)}</pre>
                </details>
              ))}
            <div className="inspector-note">
              <span className="dot green" />
              State is committed before display.
            </div>
          </>
        )}
        {tab === "Diff" && (
          <>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">WORKSPACE</div>
                <h3>Current diff</h3>
              </div>
              <button
                aria-label="Refresh diff"
                disabled={pendingActions}
                onClick={() => action("diff")}
              >
                <RefreshCw size={14} />
              </button>
            </div>
            <p className="muted small">
              Includes user edits made before or during the run.
            </p>
            {["staged", "unstaged", "untracked"].map((k) => (
              <details className="diff-group" key={k} open>
                <summary>{label(k)} changes</summary>
                <pre className="diff-code">
                  {session.inspection.diff?.[k] ||
                    "No changes loaded. Refresh to inspect."}
                </pre>
              </details>
            ))}
          </>
        )}
        {tab === "Sandbox" && (
          <>
            <div className="eyebrow">EXECUTION ENVIRONMENT</div>
            <h3>Session sandbox</h3>
            <Status value={session.sandbox.state} />
            <dl>
              {Object.entries({
                Image: session.sandbox.image,
                Container: session.sandbox.container,
                Volume: session.sandbox.volume,
                Network: session.sandbox.network ? "Enabled" : "Offline",
                Limits: "2 CPUs · 2 GB · 256 processes",
              }).map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || "Not created"}</dd>
                </div>
              ))}
            </dl>
            <div className="button-row">
              {[
                ["start", "Start"],
                ["stop_sandbox", "Stop sandbox"],
                ["rebuild", "Rebuild"],
              ].map(([kind, title]) => (
                <button
                  key={kind}
                  disabled={blocked || pendingActions || busy}
                  onClick={() =>
                    kind === "rebuild"
                      ? ask(
                          "Rebuild container?",
                          "The workspace volume remains. Processes and container-layer changes will be lost.",
                          () => action(kind),
                        )
                      : action(kind)
                  }
                >
                  {title}
                </button>
              ))}
            </div>
            <button
              className="wide"
              disabled={blocked || pendingActions || busy}
              onClick={() =>
                ask(
                  "Change sandbox network?",
                  "This applies and verifies a Docker network change. The container may be recreated; its volume remains.",
                  () =>
                    action("network", {
                      enabled: !session.sandbox.network,
                    }),
                )
              }
            >
              {session.sandbox.network ? "Disable network" : "Enable network"}
            </button>
            <p className="muted small">
              Remote HTTP MCP runs from the agent service. Network changes are
              available between runs.
            </p>
          </>
        )}
        {tab === "Extensions" && (
          <>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">REPOSITORY CONFIGURATION</div>
                <h3>Extensions & trust</h3>
              </div>
              <button
                disabled={pendingActions}
                onClick={() => action("extensions")}
                aria-label="Discover extensions"
              >
                <RefreshCw size={14} />
              </button>
            </div>
            <p className="muted small">
              Discovery does not activate repository content.
            </p>
            {Object.entries(session.inspection.extensions || {}).map(
              ([category, pkg]: [string, any]) => (
                <div className="extension-card" key={category}>
                  <h4>{label(category)}</h4>
                  <Status
                    value={
                      session.trust[category] === pkg.identity
                        ? "trusted"
                        : session.trust[category]
                          ? "changed"
                          : "untrusted"
                    }
                  />
                  {Object.entries(pkg.contents || {}).map(([path, text]) => (
                    <details key={path}>
                      <summary className="mono">{path}</summary>
                      <pre>{String(text)}</pre>
                    </details>
                  ))}
                  <button
                    disabled={blocked || busy}
                    onClick={() =>
                      ask(
                        "Trust " + category + "?",
                        "Trust these files and their current content identity. Tool approvals still apply.",
                        () =>
                          action("trust", {
                            category,
                            identity: pkg.identity,
                          }),
                      )
                    }
                  >
                    Inspect & trust
                  </button>
                </div>
              ),
            )}
            {!session.inspection.extensions && (
              <p className="inspector-empty">
                Discover repository Skills, MCP, and instruction files.
              </p>
            )}
          </>
        )}
        {session.actions
          .filter((a) => a.status === "failed")
          .slice(-1)
          .map((a) => (
            <div className="error-banner" key={a.id}>
              {a.error}
            </div>
          ))}
      </div>
      <footer className="inspector-footer">
        <ShieldCheck size={14} />
        Single user · Explicit permissions
      </footer>
    </aside>
  );
}
