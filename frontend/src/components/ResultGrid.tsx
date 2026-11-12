import { AgGridReact } from "ag-grid-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { QueryResult } from "../api";
import { columnDefs, gridLocale, toRecords, useGridTheme } from "../lib/grid";

/** Client-side grid for query results (already limited by the backend). */
export default function ResultGrid({ result }: { result: QueryResult }) {
  const { t, i18n } = useTranslation();
  const theme = useGridTheme();
  const defs = useMemo(() => {
    const masked = new Set(result.masked);
    return columnDefs(
      result.columns.map((name, i) => {
        const sample = result.rows.find((r) => r[i] !== null && r[i] !== undefined)?.[i];
        const type = typeof sample === "number" ? "REAL" : "TEXT";
        return { name, type, masked: masked.has(name) };
      }),
      t("explore.masked"),
    ).map((d, i) => {
      const name = result.columns[i];
      const label = t(`dash.labels.${name}`, { defaultValue: name });
      return {
        ...d,
        field: `c${i}`,
        sortable: true,
        headerName: masked.has(name) ? `🔒 ${label}` : label,
        headerTooltip: label === name ? d.headerTooltip : name,
      };
    });
  }, [result, t]);
  const rows = useMemo(
    () => toRecords(result.columns.map((_, i) => `c${i}`), result.rows),
    [result],
  );
  return (
    <AgGridReact
      theme={theme}
      localeText={gridLocale(i18n.language)}
      columnDefs={defs}
      rowData={rows}
      defaultColDef={{ resizable: true }}
      enableCellTextSelection
      tooltipShowDelay={300}
    />
  );
}
