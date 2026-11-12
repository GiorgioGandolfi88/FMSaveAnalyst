// Chart colours and ink, from the validated reference palette (dataviz skill, palette.md).
// Categorical slots are assigned in this fixed order and never cycled; light and dark are
// separately validated steps of the same hues.

export interface VizTheme {
  series: string[];
  surface: string;
  ink: string;
  inkSecondary: string;
  muted: string;
  grid: string;
  axis: string;
  sequential: string;
}

export const LIGHT: VizTheme = {
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  surface: "#fcfcfb",
  ink: "#0b0b0b",
  inkSecondary: "#52514e",
  muted: "#898781",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  sequential: "#2a78d6",
};

export const DARK: VizTheme = {
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  surface: "#1a1a19",
  ink: "#f0efec",
  inkSecondary: "#c3c2b7",
  muted: "#898781",
  grid: "#2c2c2a",
  axis: "#383835",
  sequential: "#3987e5",
};

/** Line charts carry at most this many series (adjacent-pair validated); more go to "Other". */
export const MAX_LINE_SERIES = 6;

export function compact(value: number, language: string): string {
  return new Intl.NumberFormat(language, {
    notation: Math.abs(value) >= 10000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(value) >= 10000 ? 1 : 2,
  }).format(value);
}

export function full(value: number, language: string): string {
  return new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(value);
}
