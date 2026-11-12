import { useComputedColorScheme } from "@mantine/core";
import {
  AllCommunityModule,
  colorSchemeDarkBlue,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
} from "ag-grid-community";
import { AG_GRID_LOCALE_IT } from "./gridLocaleIt";
import type { SchemaColumn } from "../api";

ModuleRegistry.registerModules([AllCommunityModule]);

const light = themeQuartz.withParams({ fontFamily: "inherit", headerFontWeight: 600 });
const dark = light.withPart(colorSchemeDarkBlue);

export function useGridTheme() {
  return useComputedColorScheme("light") === "dark" ? dark : light;
}

export function gridLocale(language: string) {
  return language.startsWith("it") ? AG_GRID_LOCALE_IT : undefined;
}

const DATE_NAME = /(^|_)(date|start|end|month|loan_start|loan_end)$|_date$/;

export function filterFor(column: Pick<SchemaColumn, "name" | "type">): string {
  const type = column.type.toUpperCase();
  if (type === "INTEGER" || type === "REAL") return "agNumberColumnFilter";
  if (DATE_NAME.test(column.name)) return "agDateColumnFilter";
  return "agTextColumnFilter";
}

export function columnDefs(
  columns: Pick<SchemaColumn, "name" | "type" | "masked">[],
  maskedLabel: string,
): ColDef[] {
  return columns.map((c) => ({
    field: c.name,
    headerName: c.masked ? `🔒 ${c.name}` : c.name,
    headerTooltip: c.masked ? maskedLabel : undefined,
    filter: c.masked ? false : filterFor(c),
    sortable: !c.masked,
    minWidth: 90,
    cellClass: c.type.toUpperCase() === "TEXT" ? undefined : "ag-right-aligned-cell",
    filterParams: {
      buttons: ["reset", "apply"],
      closeOnApply: true,
      maxNumConditions: 2,
    },
  }));
}

/** Turn [[a, b], ...] rows into objects keyed by column, as AG Grid expects. */
export function toRecords(columns: string[], rows: unknown[][]): Record<string, unknown>[] {
  return rows.map((r) => {
    const o: Record<string, unknown> = {};
    columns.forEach((c, i) => (o[c] = r[i]));
    return o;
  });
}
