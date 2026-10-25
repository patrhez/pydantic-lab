import React, { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  FileDiff,
  FolderGit2,
  Layers,
  LoaderCircle,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Square,
  Terminal,
  Trash2,
  X,
} from "lucide-react";
import {
  Approval,
  Run,
  Session,
  activeRun,
  canSend,
  label,
  uuid,
} from "./types";
import { Status } from "./components/Status";
import { ApprovalCard, RunView } from "./components/Chat";
import { Modal } from "./components/Modal";
import { Inspector } from "./components/Inspector";
import "./style.css";

async function api(path: string, body?: unknown) {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Service unavailable" }));
    throw new Error(data.detail || response.statusText);
  }
  return response.json();
}
export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]),
    [selected, setSelected] = useState<string | null>(
      () => location.pathname.split("/sessions/")[1] || null,
    );
  const [session, setSession] = useState<Session | null>(null),
    [draft, setDraft] = useState(""),
    [mode, setMode] = useState<"queue" | "steer">("queue");
  const [connected, setConnected] = useState(false),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Trace"),
    [newOpen, setNewOpen] = useState(false),
    [rail, setRail] = useState(false);
  const [busy, setBusy] = useState(false),
    [newActivity, setNewActivity] = useState(false);
  const [confirm, setConfirm] = useState<{
      title: string;
      message: string;
      typed?: boolean;
      action: () => Promise<void>;
    } | null>(null),
    [typed, setTyped] = useState("");
  const [form, setForm] = useState({
    repository: "",
    branch: "",
    commit: "",
    title: "",
    init_commands: "",
  });
  const bottom = useRef<HTMLDivElement>(null),
    scroller = useRef<HTMLDivElement>(null),
    composer = useRef<HTMLTextAreaElement>(null),
    atBottom = useRef(true),
    busyRef = useRef(false),
    retryIds = useRef<Record<string, string>>({});
  const inspection = useRef<Record<string, Record<string, unknown>>>({});
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const approvalCount = useRef(0);
  const list = async () => {
    try {
      setSessions(await api("/sessions"));
    } catch (e) {
      setError(String(e));
    }
  };
  const refresh = async (sid: string) => {
    const snap = await api("/sessions/" + sid);
    if (selectedRef.current !== sid) return snap;
    setSession({
      ...snap.session,
      inspection: inspection.current[sid] || {},
      records: snap.events || [],
    });
    setSessions((old) => old.map((s) => (s.id === sid ? snap.session : s)));
    return snap;
  };
  useEffect(() => {
    list();
    const timer = setInterval(list, 3000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!selected) {
      setSession(null);
      return;
    }
    setDraft(localStorage.getItem("draft:" + selected) || "");
    setMode("queue");
    setRail(false);
    setError("");
    let cancelled = false,
      source: EventSource | null = null,
      timeout: ReturnType<typeof setTimeout>,
      refreshTimer: ReturnType<typeof setTimeout> | null = null,
      attempt = 0,
      cursor = 0;
    const connect = () => {
      if (cancelled) return;
      source = new EventSource(
        `/api/sessions/${selected}/events?after=${cursor}`,
      );
      source.onopen = () => {
        attempt = 0;
        setConnected(true);
      };
      source.onmessage = (event) => {
        const next = Number(event.lastEventId);
        if (next <= cursor) return;
        cursor = next;
        if (!refreshTimer)
          refreshTimer = setTimeout(() => {
            refreshTimer = null;
            if (!cancelled) refresh(selected).catch((e) => setError(String(e)));
          }, 80);
      };
      source.onerror = () => {
        source?.close();
        setConnected(false);
        const delay = Math.min(30000, 1000 * 2 ** attempt++);
        timeout = setTimeout(connect, delay * (0.8 + Math.random() * 0.2));
      };
    };
    refresh(selected)
      .then((snap) => {
        if (!cancelled) {
          cursor = snap.cursor;
          connect();
        }
      })
      .catch((e) => setError(String(e)));
    return () => {
      cancelled = true;
      source?.close();
      clearTimeout(timeout);
      if (refreshTimer) clearTimeout(refreshTimer);
    };
  }, [selected]);
  useEffect(() => {
    if (session && (!activeRun(session) || activeRun(session)?.stop_requested))
      setMode("queue");
  }, [session?.status, session?.paused]);
  useEffect(() => {
    if (atBottom.current) {
      bottom.current?.scrollIntoView({ behavior: "instant" });
      setNewActivity(false);
    } else setNewActivity(true);
    const count = session
      ? session.setup_approvals.filter((a) => a.status === "pending").length +
        session.runs
          .flatMap((r) => r.approvals)
          .filter((a) => a.status === "pending").length
      : 0;
    approvalCount.current = count;
  }, [session]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const editable = (event.target as HTMLElement)?.matches(
        "input,textarea,[contenteditable=true]",
      );
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setNewOpen(true);
      } else if (event.key === "/" && !editable) {
        event.preventDefault();
        composer.current?.focus();
      } else if (event.key === "Escape") {
        setRail(false);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const choose = (id: string) => {
    setSelected(id);
    history.pushState({}, "", `/sessions/${id}`);
  };
  const submit = async (
    key: string,
    fn: (request_id: string) => Promise<unknown>,
  ) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    const id = retryIds.current[key] || (retryIds.current[key] = uuid());
    try {
      await fn(id);
      delete retryIds.current[key];
      if (selected) await refresh(selected);
      await list();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const action = async (
    kind: string,
    payload: Record<string, unknown> = {},
  ) => {
    if (["diff", "extensions"].includes(kind)) {
      const sid = selected!;
      try {
        const result = await api(`/sessions/${sid}/workspace/${kind}`);
        inspection.current[sid] = {
          ...inspection.current[sid],
          [kind]: result,
        };
        await refresh(sid);
      } catch (e) {
        setError(String(e));
      }
      return;
    }
    await submit("action:" + kind + JSON.stringify(payload), (id) =>
      api(`/sessions/${selected}/actions`, { kind, payload, request_id: id }),
    );
  };
  const decide = (a: Approval, allow: boolean) =>
    submit("approval:" + a.id, (id) =>
      api(`/sessions/${selected}/approvals/${a.id}`, { allow, request_id: id }),
    );
  const send = () => {
    if (!session || !draft.trim() || !canSend(session) || busy) return;
    const text = draft;
    submit("message:" + mode + text, async (id) => {
      await api(`/sessions/${selected}/messages`, {
        content: text,
        mode,
        request_id: id,
      });
      if (localStorage.getItem("draft:" + selected) === text)
        localStorage.removeItem("draft:" + selected);
      if (selectedRef.current === selected)
        setDraft((current) => (current === text ? "" : current));
    });
  };
  const ask = (
    title: string,
    message: string,
    fn: () => Promise<void>,
    typed = false,
  ) => {
    setTyped("");
    setConfirm({ title, message, action: fn, typed });
  };
  const active = session ? activeRun(session) : null,
    approvals = session
      ? [
          ...session.setup_approvals,
          ...session.runs.flatMap((r) => r.approvals),
        ].filter((a) => a.status === "pending")
      : [];
  const pendingActions = session?.actions.some((a) =>
    ["queued", "running"].includes(a.status),
  );
  const queueCount =
    session?.runs.filter((r) => r.status === "queued").length || 0;
  const blocked = !!active || session?.status === "provisioning";
  const reviewApproval = () => {
    document.getElementById("approval-" + approvals[0]?.id)?.focus();
    document
      .getElementById("approval-" + approvals[0]?.id)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  };
  return (
    <div className="app-shell">
      <aside className={"session-rail " + (rail ? "mobile-open" : "")}>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            setSelected(null);
            history.pushState({}, "", "/");
          }}
        >
          <span className="brand-icon">
            <Layers size={20} />
          </span>
          Pydantic Lab<span className="lab-badge">LAB</span>
        </a>
        <button className="new-session" onClick={() => setNewOpen(true)}>
          <Plus size={16} />
          New session<span className="shortcut">⌘ K</span>
        </button>
        <div className="section-label">
          WORKSPACES <span>{sessions.length}</span>
        </div>
        <nav aria-label="Sessions">
          {sessions.map((s) => (
            <button
              key={s.id}
              className={"session-row " + (s.id === selected ? "selected" : "")}
              onClick={() => choose(s.id)}
            >
              <div>
                <FolderGit2 size={16} />
                <strong>{s.title}</strong>
                <MoreHorizontal size={16} />
              </div>
              <div className="row-status">
                <Status value={s.status} />
                {s.runs.filter((r) => r.status === "queued").length > 0 && (
                  <span className="small">
                    {s.runs.filter((r) => r.status === "queued").length} queued
                  </span>
                )}
              </div>
              <span className="repo-label">
                {s.branch || s.commit?.slice(0, 7) || "Resolving revision"}
              </span>
            </button>
          ))}
        </nav>
        {!sessions.length && (
          <p className="rail-empty">
            Create a session to work on a public Git repository.
          </p>
        )}
        <div className="rail-footer">
          <span className={"dot " + (connected ? "green" : "")} />
          <span>
            {selected
              ? connected
                ? "Connected"
                : "Reconnecting"
              : "Local development"}
          </span>
          <span className="version">v0.1</span>
        </div>
      </aside>
      <main className="workspace">
        {!session ? (
          <div className="welcome">
            <div className="welcome-icon">
              <Code2 size={36} />
            </div>
            <span className="eyebrow">YOUR AGENT WORKSPACE</span>
            <h1>A clear view of every step.</h1>
            <p>
              Explore code, review operations, and follow the agent loop.
              <br />
              Each session runs in its own Docker workspace.
            </p>
            <button className="primary" onClick={() => setNewOpen(true)}>
              <Plus size={16} />
              Create a session
            </button>
            <div className="welcome-features">
              <span>
                <ShieldCheck size={16} />
                Explicit approvals
              </span>
              <span>
                <Terminal size={16} />
                Isolated execution
              </span>
              <span>
                <RefreshCw size={16} />
                Durable recovery
              </span>
            </div>
          </div>
        ) : (
          <>
            <header className="workspace-header">
              <button
                className="icon-button mobile-menu"
                aria-label="Open sessions"
                onClick={() => setRail(!rail)}
              >
                <Menu size={20} />
              </button>
              <div className="workspace-name">
                <h1>
                  <FolderGit2 size={19} />
                  {session.title}
                </h1>
                <div className="header-meta">
                  <span>{session.branch || "detached"}</span>
                  <span>·</span>
                  <span className="mono">
                    {session.commit?.slice(0, 8) || "initializing"}
                  </span>
                  <Status value={session.status} />
                </div>
              </div>
              <div className="header-actions">
                <button
                  disabled={!active || busy}
                  className="stop-button"
                  onClick={() =>
                    submit("stop", (id) =>
                      api(`/sessions/${selected}/stop`, { request_id: id }),
                    )
                  }
                >
                  <Square size={12} />
                  Stop
                </button>
                <button
                  disabled={!session.paused || !!active || busy}
                  onClick={() =>
                    submit("continue", (id) =>
                      api(`/sessions/${selected}/continue`, { request_id: id }),
                    )
                  }
                >
                  Continue
                </button>
                <button
                  className="icon-button"
                  aria-label="Delete session"
                  disabled={blocked || busy}
                  title={
                    blocked
                      ? "Stop execution before deleting"
                      : "Delete session"
                  }
                  onClick={() =>
                    ask(
                      "Delete this session?",
                      "The session and its workspace volume will be removed permanently. Type DELETE to confirm.",
                      () => action("delete", { confirmation: "DELETE" }),
                      true,
                    )
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </header>
            {error && (
              <div className="error-banner" role="alert">
                {error}
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={14} />
                </button>
              </div>
            )}
            <div className="workspace-columns">
              <section className="conversation">
                <div
                  className="transcript"
                  ref={scroller}
                  onScroll={() => {
                    const e = scroller.current!;
                    atBottom.current =
                      e.scrollHeight - e.scrollTop - e.clientHeight < 100;
                  }}
                >
                  <div className="session-intro">
                    <div className="eyebrow">
                      <span className="dot green" />
                      ISOLATED WORKSPACE
                    </div>
                    <h2>Let's work on {session.title}.</h2>
                    <p>
                      The agent can inspect code and propose changes. You stay
                      in control of execution.
                    </p>
                  </div>
                  {session.status === "provisioning" && (
                    <div className="notice">
                      <LoaderCircle size={17} className="spin" />
                      <div>
                        <strong>Preparing workspace</strong>
                        <p>
                          {approvals.length
                            ? "Setup is waiting for your approval."
                            : "Cloning the public repository and running approved setup."}
                        </p>
                      </div>
                    </div>
                  )}
                  {session.error && (
                    <div className="error-banner">{session.error}</div>
                  )}
                  {session.setup_approvals.map((a) => (
                    <ApprovalCard key={a.id} approval={a} onDecide={decide} />
                  ))}
                  {session.runs.map((r) => (
                    <RunView key={r.id} run={r} onDecide={decide} />
                  ))}
                  {session.status === "outcome_unknown" && (
                    <div className="recovery-panel">
                      <div className="eyebrow amber">RECOVERY REQUIRED</div>
                      <h3>Outcome unknown</h3>
                      <p>
                        An operation started without a confirmed receipt.
                        Inspect the current diff and output before choosing an
                        action.
                      </p>
                      <div className="button-row">
                        {[
                          ["continue", "Continue without retry"],
                          ["retry", "Retry once"],
                          ["abort", "Abort"],
                        ].map(([kind, title]) => (
                          <button
                            key={kind}
                            onClick={() =>
                              ask(
                                title,
                                kind === "retry"
                                  ? "The first attempt may already have changed files. Repeating it can duplicate effects."
                                  : "Your decision does not roll back files. Continuing reports a manually inspected, unknown outcome.",
                                () =>
                                  submit("recovery:" + kind, (id) =>
                                    api(`/sessions/${selected}/recovery`, {
                                      action: kind,
                                      confirmed: true,
                                      request_id: id,
                                    }),
                                  ),
                              )
                            }
                          >
                            {title}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div ref={bottom} />
                </div>
                {newActivity && (
                  <button
                    className="activity-pill"
                    onClick={() => {
                      atBottom.current = true;
                      bottom.current?.scrollIntoView({ behavior: "smooth" });
                      setNewActivity(false);
                    }}
                  >
                    <ArrowDown size={14} />
                    New activity
                  </button>
                )}
                <div className="composer-wrap">
                  {approvals.length > 0 && (
                    <div className="approval-notification" role="status">
                      <ShieldCheck size={14} />
                      {approvals.length} operation
                      {approvals.length > 1 ? "s" : ""} waiting for approval
                      <button onClick={reviewApproval}>
                        Review approval
                        <ArrowUpRight size={13} />
                      </button>
                    </div>
                  )}
                  {session.paused && (
                    <div className="paused-note">
                      Queue is paused. Continue starts the next queued run.
                    </div>
                  )}
                  <div className="composer-box">
                    <textarea
                      ref={composer}
                      aria-label="Message"
                      placeholder={
                        canSend(session)
                          ? "Ask the agent to explore, build, or fix something…"
                          : "Resolve the current workspace state to continue."
                      }
                      value={draft}
                      disabled={!canSend(session)}
                      onChange={(e) => {
                        setDraft(e.target.value);
                        localStorage.setItem(
                          "draft:" + selected,
                          e.target.value,
                        );
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          send();
                        }
                      }}
                    />
                    <div className="composer-toolbar">
                      <div
                        className="mode-control"
                        role="group"
                        aria-label="Message mode"
                      >
                        <button
                          aria-pressed={mode === "queue"}
                          className={mode === "queue" ? "active" : ""}
                          onClick={() => setMode("queue")}
                        >
                          Queue
                        </button>
                        <button
                          aria-pressed={mode === "steer"}
                          className={mode === "steer" ? "active" : ""}
                          disabled={!active || active.stop_requested}
                          onClick={() => setMode("steer")}
                        >
                          Steer
                        </button>
                      </div>
                      <span className="composer-hint">
                        {mode === "steer"
                          ? "At the next safe boundary"
                          : "After the current run"}
                      </span>
                      <button
                        className="send-button"
                        aria-label="Send message"
                        disabled={!draft.trim() || !canSend(session) || busy}
                        onClick={send}
                      >
                        <ArrowUpRight size={18} />
                      </button>
                    </div>
                  </div>
                  <div className="composer-footnote">
                    <span>Enter to send · Shift + Enter for a new line</span>
                    <span>
                      {queueCount > 0
                        ? `${queueCount} queued`
                        : "Pydantic AI · Docker sandbox"}
                    </span>
                  </div>
                </div>
              </section>
              <Inspector
                session={session}
                tab={tab}
                setTab={setTab}
                pendingActions={pendingActions}
                blocked={blocked}
                busy={busy}
                refresh={refresh}
                action={action}
                ask={ask}
              />
            </div>
          </>
        )}
      </main>
      {newOpen && (
        <Modal title="Create a session" onClose={() => setNewOpen(false)}>
          <p className="muted">
            Start an isolated workspace from a public Git repository.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit("create:" + JSON.stringify(form), async (id) => {
                const s = await api("/sessions", {
                  ...form,
                  branch: form.branch || null,
                  commit: form.commit || null,
                  init_commands: form.init_commands.split("\n").filter(Boolean),
                  request_id: id,
                });
                setNewOpen(false);
                choose(s.id);
              });
            }}
          >
            <label>
              Git repository URL
              <input
                required
                type="url"
                placeholder="https://github.com/owner/repository.git"
                value={form.repository}
                onChange={(e) =>
                  setForm({ ...form, repository: e.target.value })
                }
              />
            </label>
            <div className="form-grid">
              <label>
                Branch
                <input
                  placeholder="Default branch"
                  value={form.branch}
                  onChange={(e) => setForm({ ...form, branch: e.target.value })}
                />
              </label>
              <label>
                Commit
                <input
                  placeholder="Full commit SHA"
                  value={form.commit}
                  onChange={(e) => setForm({ ...form, commit: e.target.value })}
                />
              </label>
            </div>
            {form.branch && form.commit && (
              <p role="alert" className="error-text">
                Choose a branch or a commit, not both.
              </p>
            )}
            <label>
              Session title <span className="muted">optional</span>
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <details>
              <summary>Initialization commands</summary>
              <textarea
                aria-label="Initialization commands"
                placeholder="One command per line; each requires approval."
                value={form.init_commands}
                onChange={(e) =>
                  setForm({ ...form, init_commands: e.target.value })
                }
              />
            </details>
            <p className="small muted">
              Setup can use the network. Normal execution starts offline.
            </p>
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
            <div className="modal-actions">
              <button type="button" onClick={() => setNewOpen(false)}>
                Cancel
              </button>
              <button
                className="primary"
                disabled={busy || !!(form.branch && form.commit)}
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Plus size={15} />
                )}
                Create session
              </button>
            </div>
          </form>
        </Modal>
      )}
      {confirm && (
        <Modal title={confirm.title} onClose={() => setConfirm(null)}>
          <p>{confirm.message}</p>
          {confirm.typed && (
            <input
              aria-label="Type DELETE to confirm"
              placeholder="DELETE"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          )}
          <div className="modal-actions">
            <button onClick={() => setConfirm(null)}>Cancel</button>
            <button
              className="primary"
              disabled={busy || (confirm.typed && typed !== "DELETE")}
              onClick={async () => {
                await confirm.action();
                setConfirm(null);
              }}
            >
              Confirm
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
