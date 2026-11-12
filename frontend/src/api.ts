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
};

// Native file dialogs, available only inside the desktop window (pywebview).
interface DesktopApi {
  pick_save: (folder: string) => Promise<string | null>;
  pick_career: (folder: string) => Promise<string | null>;
}

export function desktopApi(): DesktopApi | null {
  const w = window as unknown as { pywebview?: { api?: DesktopApi } };
  return w.pywebview?.api ?? null;
}
