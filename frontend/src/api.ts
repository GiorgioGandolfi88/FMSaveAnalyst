// Minimal client for the local FMSaveAnalyst API.
// The session token arrives once in the URL (?t=...), is kept in sessionStorage and removed
// from the address bar.

const TOKEN_KEY = "fmsa.token";

function initToken(): string {
  const url = new URL(window.location.href);
  const fromUrl = url.searchParams.get("t");
  if (fromUrl) {
    sessionStorage.setItem(TOKEN_KEY, fromUrl);
    url.searchParams.delete("t");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    return fromUrl;
  }
  return sessionStorage.getItem(TOKEN_KEY) ?? import.meta.env.VITE_FMSA_DEV_TOKEN ?? "";
}

const token = initToken();

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      "X-FMSA-Token": token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = JSON.stringify((await res.json()).detail ?? detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export type Language = "it" | "en";
export type AiProvider = "none" | "anthropic" | "openai" | "gemini";

export interface MaskingSettings {
  potential_ability: boolean;
  current_ability: boolean;
  hidden_attributes: boolean;
  personality: boolean;
  extra_columns: string[];
}

export interface Settings {
  schema_version: number;
  language: Language;
  fm_save_dir: string;
  careers_dir: string;
  reference_db: string;
  last_career: string;
  recent_careers: string[];
  check_updates: boolean;
  masking: MaskingSettings;
  ai: { provider: AiProvider; model: string; confirm_before_send: boolean };
}

export interface AppInfo {
  version: string;
  portable: boolean;
  app_dir: string;
  data_dir: string;
  settings_file: string;
}

export const api = {
  appInfo: () => request<AppInfo>("GET", "/app-info"),
  getSettings: () => request<Settings>("GET", "/settings"),
  saveSettings: (s: Settings) => request<Settings>("PUT", "/settings", s),
};

// ---------------------------------------------------------------- careers & imports

export interface SaveFile {
  path: string;
  name: string;
  size_mb: number;
  modified: string;
}

export interface CareerSummary {
  path: string;
  name: string;
  game: string | null;
  imports: number;
  first_game_date: string | null;
  last_game_date: string | null;
  last_save: string | null;
  manager: string | null;
  reference_version: string | null;
  size_mb: number;
  error: string | null;
}

export interface SkippedReader {
  reader: string;
  status: string;
  message: string | null;
}

export interface ImportRow {
  import_id: number;
  file_name: string;
  game_date: string | null;
  build: string;
  finished_at: string | null;
  duration_s: number | null;
  status: string;
  manager_name: string | null;
  skipped_readers: SkippedReader[];
}

export interface CareerDetail {
  summary: CareerSummary;
  imports: ImportRow[];
}

export type Verdict = "same" | "uncertain" | "different" | "incompatible";

export interface ContinuityCheck {
  id: string;
  outcome: "pass" | "fail" | "warn" | "skip";
  detail: string;
  hard: boolean;
}

export interface ContinuityReport {
  verdict: Verdict;
  save_file: string;
  save_game: string;
  save_build: string;
  save_date: string | null;
  career_date: string | null;
  checks: ContinuityCheck[];
  gap_warning: boolean;
}

export interface JobReader {
  reader: string;
  status: string;
  rows: number;
  message: string;
}

export interface Job {
  id: string;
  kind: "create" | "update";
  career_path: string;
  save_path: string;
  status: "running" | "done" | "rejected" | "failed";
  reader: string;
  done: number;
  total: number;
  elapsed_s: number;
  message: string;
  result: {
    import_id: number;
    file_name: string;
    game_date: string | null;
    seconds: number;
    reference_version: string | null;
    reference_exact: boolean;
    readers: JobReader[];
  } | null;
}

export const careersApi = {
  saves: (folder = "") =>
    request<{ folder: string; saves: SaveFile[] }>(
      "GET",
      `/saves${folder ? `?folder=${encodeURIComponent(folder)}` : ""}`,
    ),
  list: () => request<CareerSummary[]>("GET", "/careers"),
  detail: (path: string) =>
    request<CareerDetail>("GET", `/careers/detail?path=${encodeURIComponent(path)}`),
  create: (name: string, save_path: string) =>
    request<Job>("POST", "/careers", { name, save_path }),
  open: (path: string) => request<CareerSummary>("POST", "/careers/open", { path }),
  check: (career_path: string, save_path: string) =>
    request<ContinuityReport>("POST", "/careers/check", { career_path, save_path }),
  importSave: (career_path: string, save_path: string) =>
    request<Job>("POST", "/careers/import", { career_path, save_path }),
  job: (id: string) => request<Job>("GET", `/jobs/${id}`),
  importLog: (path: string, importId: number) =>
    request<ImportLog>(
      "GET",
      `/careers/import-log?path=${encodeURIComponent(path)}&import_id=${importId}`,
    ),
};

export interface ImportLogRow {
  seq: number;
  reader: string;
  fmsave_call: string;
  table_name: string;
  parent_table: string | null;
  storage: string;
  started_at: string | null;
  read_finished_at: string | null;
  finished_at: string | null;
  read_ms: number | null;
  write_ms: number | null;
  rows_read: number | null;
  rows_inserted: number | null;
  rows_updated: number | null;
  rows_unchanged: number | null;
  rows_closed: number | null;
  status: string;
  message: string | null;
}

export interface ImportLog {
  import: {
    import_id: number;
    file_name: string;
    started_at: string;
    finished_at: string | null;
    duration_s: number | null;
    status: string;
    log_file: string | null;
  } | null;
  rows: ImportLogRow[];
}

// Native file dialogs, available only inside the desktop window (pywebview).
interface DesktopApi {
  pick_save: (folder: string) => Promise<string | null>;
  pick_career: (folder: string) => Promise<string | null>;
  pick_export_path?: (fileName: string) => Promise<string | null>;
}

export function desktopApi(): DesktopApi | null {
  const w = window as unknown as { pywebview?: { api?: DesktopApi } };
  return w.pywebview?.api ?? null;
}

// ---------------------------------------------------------------- schema, queries, export

export interface SchemaColumn {
  name: string;
  type: string;
  masked: boolean;
  source_path: string;
  status: string;
  internal: boolean;
}

export interface SchemaObject {
  name: string;
  type: "table" | "view";
  group: "data" | "records" | "history" | "reference" | "derived";
  kind: string | null;
  reader: string | null;
  parent: string | null;
  columns: SchemaColumn[];
}

export interface Relation {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
}

export interface Schema {
  career: string;
  objects: SchemaObject[];
  relations: Relation[];
}

export interface QueryResult {
  columns: string[];
  rows: unknown[][];
  truncated: boolean;
  elapsed_ms: number;
  masked: string[];
  row_count: number;
}

export interface BrowseRequest {
  table: string;
  columns?: string[] | null;
  filter_model?: Record<string, unknown>;
  sort_model?: { colId: string; sort: string }[];
  start?: number;
  end?: number;
  count?: boolean;
}

export interface BrowseResult extends QueryResult {
  total: number | null;
  sql: string;
  params: unknown[];
}

export type ExportFormat = "csv" | "csv_excel" | "json";

export interface SavedQuery {
  name: string;
  sql: string;
  model: Record<string, unknown> | null;
}

export const dataApi = {
  schema: () => request<Schema>("GET", "/schema"),
  query: (sql: string, limit = 10000) => request<QueryResult>("POST", "/query", { sql, limit }),
  browse: (body: BrowseRequest) => request<BrowseResult>("POST", "/browse", body),
  savedQueries: () => request<SavedQuery[]>("GET", "/saved-queries"),
  saveQueries: (q: SavedQuery[]) => request<SavedQuery[]>("PUT", "/saved-queries", q),
};

const EXT: Record<ExportFormat, string> = { csv: "csv", csv_excel: "csv", json: "json" };

/** Export a query or a grid view. In the desktop window a native "save as" dialog is used. */
export async function exportData(
  body: { sql?: string; browse?: BrowseRequest; params?: Record<string, unknown> },
  format: ExportFormat,
  baseName: string,
): Promise<string | null> {
  const fileName = `${baseName}.${EXT[format]}`;
  const desktop = desktopApi();
  if (desktop?.pick_export_path) {
    const path = await desktop.pick_export_path(fileName);
    if (!path) return null;
    const r = await request<{ path: string; rows: number }>("POST", "/export", {
      ...body,
      format,
      path,
    });
    return r.path;
  }
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "X-FMSA-Token": token, "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, format }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
  return fileName;
}

// ---------------------------------------------------------------- dashboards

export type Localized = Record<string, string>;

export interface DashboardInput {
  id: string;
  default: number;
  min?: number;
  max?: number;
  label: Localized;
}

export interface DashboardSummary {
  id: string;
  title: Localized;
  description: Localized;
  params: string[];
  inputs?: DashboardInput[];
  source: "builtin" | "user";
  widgets: number;
}

export interface DashboardWidget {
  id: string;
  type: "kpi" | "table" | "bar" | "line" | "scatter";
  title: Localized;
  sql: string;
  span?: number;
  format?: "int" | "decimal" | "money" | "text";
  x?: string;
  y?: string | string[];
  series?: string;
  label?: string;
  horizontal?: boolean;
  stacked?: boolean;
  invert_y?: boolean;
}

export interface Dashboard extends Omit<DashboardSummary, "widgets"> {
  widgets: DashboardWidget[];
}

export interface ParamOption {
  value: string | number;
  label: string;
  nation?: number | null; // club options: the club's nation
  leagues?: number[]; // club options: competitions of the league tables it plays in
}

export interface ParamChoices {
  options: ParamOption[];
  default: number | null;
}

export interface DashboardParams {
  club: ParamChoices;
  competition: ParamChoices;
  season: ParamChoices;
  nation: ParamChoices;
  league: ParamChoices;
  today: string | null;
}

export type WidgetData = QueryResult | { error: string };

export const dashboardsApi = {
  list: () => request<DashboardSummary[]>("GET", "/dashboards"),
  params: () => request<DashboardParams>("GET", "/dashboards/params"),
  get: (id: string) => request<Dashboard>("GET", `/dashboards/${id}`),
  data: (id: string, params: Record<string, unknown>) =>
    request<{ widgets: Record<string, WidgetData> }>("POST", `/dashboards/${id}/data`, { params }),
};

export function localized(text: Localized | undefined, language: string): string {
  if (!text) return "";
  return text[language.slice(0, 2)] ?? text.en ?? Object.values(text)[0] ?? "";
}

/** Export a whole dashboard as a zip (one file per widget). */
export async function exportDashboard(
  id: string,
  params: Record<string, unknown>,
  format: ExportFormat,
): Promise<string | null> {
  const fileName = `${id}.zip`;
  const desktop = desktopApi();
  if (desktop?.pick_export_path) {
    const path = await desktop.pick_export_path(fileName);
    if (!path) return null;
    const r = await request<{ path: string }>("POST", `/dashboards/${id}/export`, {
      params,
      format,
      path,
    });
    return r.path;
  }
  const res = await fetch(`/api/dashboards/${id}/export`, {
    method: "POST",
    headers: { "X-FMSA-Token": token, "Content-Type": "application/json" },
    body: JSON.stringify({ params, format }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
  return fileName;
}

// ---------------------------------------------------------------- AI assistants

export interface AgentInfo {
  id: string;
  name: Localized;
  description: Localized;
}

export interface AiStatus {
  provider: AiProvider;
  model: string;
  confirm_before_send: boolean;
  keys: Record<"anthropic" | "openai" | "gemini", boolean>;
  default_models: Record<string, string>;
  agents: AgentInfo[];
}

export type ChatEvent =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string }
  | { type: "error"; text: string }
  | {
      type: "tool";
      id: string;
      name: string;
      args: Record<string, unknown>;
      preview: {
        kind: string;
        columns?: string[];
        rows?: unknown[][];
        row_count?: number;
        truncated?: boolean;
        table?: string;
        count?: number;
        message?: string;
      };
      chars: number;
      status: "pending" | "sent" | "declined";
      error: boolean;
    };

export interface Chat {
  id: string;
  agent: string;
  provider: string;
  model: string;
  confirm: boolean;
  status: "idle" | "needs_approval";
  events: ChatEvent[];
  usage: { input_tokens: number; output_tokens: number; sent_chars: number };
}

export const aiApi = {
  status: () => request<AiStatus>("GET", "/ai/status"),
  saveKey: (provider: string, key: string) =>
    request<{ saved: boolean }>("PUT", "/ai/key", { provider, key }),
  deleteKey: (provider: string) => request<{ deleted: boolean }>("DELETE", `/ai/key/${provider}`),
  test: (provider: string) =>
    request<{ ok: boolean; models: string[] }>("POST", "/ai/test", { provider }),
  newChat: (agent: string) => request<Chat>("POST", "/ai/chats", { agent }),
  send: (id: string, text: string) => request<Chat>("POST", `/ai/chats/${id}/messages`, { text }),
  approve: (id: string, approve: boolean) =>
    request<Chat>("POST", `/ai/chats/${id}/approval`, { approve }),
  close: (id: string) => request<{ closed: boolean }>("DELETE", `/ai/chats/${id}`),
};

// ---------------------------------------------------------------- updates

export interface UpdateInfo {
  current: string;
  latest?: string | null;
  update_available: boolean;
  url?: string;
  notes?: string;
  published_at?: string | null;
  download_url?: string | null;
  error?: string | null;
  disabled?: boolean;
}

export const updatesApi = {
  check: (force = false) => request<UpdateInfo>("GET", `/updates${force ? "?force=true" : ""}`),
};

/** Open a GitHub page in the system browser (desktop window) or a new tab. */
export function openExternal(url: string): void {
  const w = window as unknown as { pywebview?: { api?: { open_url?: (u: string) => unknown } } };
  if (w.pywebview?.api?.open_url) void w.pywebview.api.open_url(url);
  else window.open(url, "_blank", "noopener");
}
