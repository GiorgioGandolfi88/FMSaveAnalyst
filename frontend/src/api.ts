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
