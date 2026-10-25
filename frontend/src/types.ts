export type Approval = {
  id: string;
  call_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  status: string;
  reason: string;
  setup: boolean;
};
export type Receipt = {
  call_id: string;
  tool: string;
  status: string;
  result: unknown;
  duration_ms: number | null;
};
export type Run = {
  id: string;
  prompt: string;
  status: string;
  answer: string;
  error: string | null;
  stop_requested: boolean;
  approvals: Approval[];
  receipts: Record<string, Receipt>;
  native_ids: string[];
  steers: { id: string; content: string; consumed: boolean }[];
};
export type Session = {
  records?: Record<string, any>[];
  id: string;
  title: string;
  repository: string;
  branch: string | null;
  commit: string | null;
  status: string;
  initialized: boolean;
  paused: boolean;
  error: string | null;
  updated_at: number;
  runs: Run[];
  setup_approvals: Approval[];
  sandbox: {
    id: string;
    container: string | null;
    volume: string | null;
    state: string;
    network: boolean;
    image: string;
  };
  trust: Record<string, string>;
  inspection: Record<string, any>;
  actions: { id: string; kind: string; status: string; error?: string }[];
};
export const activeRun = (s: Session) =>
  s.runs.find((r) =>
    ["running", "awaiting_approval", "outcome_unknown"].includes(r.status),
  );
export const label = (text: string) => text.replaceAll("_", " ");
export const canSend = (s: Session) =>
  s.initialized === true &&
  ![
    "provisioning",
    "deleting",
    "deleted",
    "cleanup_failed",
    "outcome_unknown",
  ].includes(s.status);
export const uuid = () => crypto.randomUUID();
