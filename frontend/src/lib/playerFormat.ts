/** Formatting helpers for the player list and card. */

const ROLE_ORDER = ["GK", "SW", "D", "WB", "DM", "M", "AM", "ST"];
const SIDE_ORDER = ["R", "L", "C"];

function splitPosition(pos: string): [string, string] {
  if (pos === "GK" || pos === "SW" || pos === "DM") return [pos, ""];
  if (pos === "STC") return ["ST", "C"];
  const m = /^(WB|AM|D|M)([LRC])$/.exec(pos);
  return m ? [m[1], m[2]] : [pos, ""];
}

/** ["AML","AMR"] -> "AM RL"; ["MR","AMR"] -> "M/AM R"; ["AML","STC"] -> "AM L, ST C". */
export function formatPositions(positions: string[]): string {
  const sides = new Map<string, Set<string>>();
  for (const p of positions) {
    const [role, side] = splitPosition(p);
    if (!sides.has(role)) sides.set(role, new Set());
    if (side) sides.get(role)!.add(side);
  }
  const roles = [...sides.keys()].sort((a, b) => ROLE_ORDER.indexOf(a) - ROLE_ORDER.indexOf(b));
  const bySides = new Map<string, string[]>();
  for (const role of roles) {
    const key = SIDE_ORDER.filter((s) => sides.get(role)!.has(s)).join("");
    bySides.set(key, [...(bySides.get(key) ?? []), role]);
  }
  return [...bySides.entries()]
    .map(([s, rs]) => (s ? `${rs.join("/")} ${s}` : rs.join("/")))
    .join(", ");
}

/** "AML" -> "AM (L)" for the card subtitle. */
export function formatPositionLong(positions: string[]): string {
  return positions
    .map((p) => {
      const [role, side] = splitPosition(p);
      return side ? `${role} (${side})` : role;
    })
    .join(", ");
}

export function money(v: number | null | undefined, lang: string): string {
  if (v === null || v === undefined) return "–";
  const abs = Math.abs(v);
  const fmt = (x: number, digits: number) =>
    x.toLocaleString(lang, { maximumFractionDigits: digits });
  if (abs >= 1e9) return `${fmt(v / 1e9, 1)}B`;
  if (abs >= 1e6) return `${fmt(v / 1e6, abs >= 1e8 ? 0 : 1)}M`;
  if (abs >= 1e4) return `${fmt(v / 1e3, abs >= 1e5 ? 0 : 1)}K`;
  return fmt(v, 0);
}

export function longDate(iso: string | null | undefined, lang: string): string {
  if (!iso) return "–";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang, { day: "numeric", month: "short", year: "numeric" });
}

export function monthYear(iso: string | null | undefined, lang: string): string {
  if (!iso) return "–";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang, { month: "short", year: "numeric" });
}

export function num(v: number | null | undefined, lang: string, digits = 0): string {
  if (v === null || v === undefined) return "–";
  return v.toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function ordinal(n: number, lang: string): string {
  if (lang.startsWith("it")) return `${n}°`;
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th");
  return `${n}${s}`;
}

/** "runs_with_ball_often" -> "Runs with ball often" */
export function prettify(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const SECTION_COLORS: Record<string, string> = {
  technical: "#d64545",
  mental: "#2f5fd0",
  physical: "#1f8a5b",
  goalkeeping: "#d99a1e",
  hidden: "#8a63d2",
};

/** Colour of a rank bar: low ranks lighter. */
export function rankColor(rank: number | null): string {
  if (rank === null) return "var(--mantine-color-gray-4)";
  if (rank >= 80) return "var(--mantine-color-dark-6)";
  if (rank >= 50) return "var(--mantine-color-gray-6)";
  return "var(--mantine-color-gray-4)";
}
