import { useComputedColorScheme } from "@mantine/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { QueryResult } from "../api";
import { compact, DARK, full, LIGHT, MAX_LINE_SERIES, type VizTheme } from "../lib/vizTheme";

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
  CanvasRenderer,
]);

export interface WidgetDef {
  id: string;
  type: "kpi" | "table" | "bar" | "line" | "scatter";
  x?: string;
  y?: string | string[];
  series?: string;
  label?: string;
  horizontal?: boolean;
  stacked?: boolean;
  invert_y?: boolean;
}

type Row = unknown[];

function col(result: QueryResult, name: string | undefined): number {
  return name ? result.columns.indexOf(name) : -1;
}

function axisCommon(theme: VizTheme, lang: string) {
  return {
    axisLine: { lineStyle: { color: theme.axis } },
    axisTick: { show: false },
    axisLabel: {
      color: theme.muted,
      formatter: (v: number | string) => (typeof v === "number" ? compact(v, lang) : String(v)),
    },
    splitLine: { lineStyle: { color: theme.grid, width: 1, type: "solid" as const } },
  };
}

function buildOption(
  w: WidgetDef,
  result: QueryResult,
  theme: VizTheme,
  lang: string,
  label: (key: string) => string,
): echarts.EChartsCoreOption {
  const xi = col(result, w.x);
  const rows = result.rows as Row[];
  const tooltipBase = {
    backgroundColor: theme.surface,
    borderColor: theme.axis,
    textStyle: { color: theme.ink, fontSize: 12 },
    valueFormatter: (v: unknown) => (typeof v === "number" ? full(v, lang) : String(v ?? "—")),
  };
  const text = { color: theme.inkSecondary, fontFamily: "inherit" };

  if (w.type === "scatter") {
    const yi = col(result, w.y as string);
    const li = col(result, w.label);
    return {
      textStyle: text,
      grid: { left: 48, right: 16, top: 16, bottom: 36 },
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (p: { data: Row }) =>
          `${li >= 0 ? `<b>${p.data[2]}</b><br/>` : ""}${label(w.x!)}: ${p.data[0]}<br/>${label(
            w.y as string,
          )}: ${p.data[1]}`,
      },
      xAxis: { type: "value", scale: true, name: label(w.x!), nameLocation: "middle", nameGap: 24,
               nameTextStyle: { color: theme.muted }, ...axisCommon(theme, lang) },  // prettier-ignore
      yAxis: { type: "value", scale: true, ...axisCommon(theme, lang) },
      series: [
        {
          type: "scatter",
          symbolSize: 9,
          itemStyle: { color: theme.series[0], borderColor: theme.surface, borderWidth: 2, opacity: 0.85 },
          emphasis: { scale: 1.4 },
          data: rows.map((r) => [r[xi], r[yi], li >= 0 ? r[li] : ""]),
        },
      ],
    };
  }

  // bar / line: either one or more value columns (wide) or a series column (long format)
  let categories: unknown[];
  let series: { name: string; data: unknown[] }[];
  if (w.series) {
    const si = col(result, w.series);
    const yi = col(result, w.y as string);
    categories = [...new Set(rows.map((r) => r[xi]))];
    const names = [...new Set(rows.map((r) => String(r[si])))];
    const pos = new Map(categories.map((c, i) => [c, i]));
    series = names.slice(0, MAX_LINE_SERIES).map((n) => {
      const data: unknown[] = new Array(categories.length).fill(null);
      rows.filter((r) => String(r[si]) === n).forEach((r) => (data[pos.get(r[xi])!] = r[yi]));
      return { name: label(n), data };
    });
  } else {
    const ys = Array.isArray(w.y) ? w.y : [w.y ?? ""];
    categories = rows.map((r) => r[xi]);
    series = ys.map((y) => ({ name: label(y), data: rows.map((r) => r[col(result, y)]) }));
  }

  const many = series.length > 1;
  const horizontal = w.type === "bar" && w.horizontal;
  const catAxis = {
    type: "category" as const,
    data: horizontal ? [...categories].reverse() : categories,
    ...axisCommon(theme, lang),
    splitLine: { show: false },
    axisLabel: { color: theme.muted, hideOverlap: !horizontal, width: horizontal ? 150 : undefined,
                 overflow: "truncate" as const },  // prettier-ignore
  };
  const valAxis = {
    type: "value" as const,
    inverse: w.invert_y ?? false,
    scale: w.type === "line", // bars start at zero; lines zoom on their range
    minInterval: 1,
    ...axisCommon(theme, lang),
  };

  return {
    backgroundColor: "transparent",
    textStyle: text,
    color: theme.series,
    grid: { left: horizontal ? 160 : 48, right: 24, top: many ? 36 : 16, bottom: 32 },
    legend: many
      ? { top: 0, left: 0, icon: "roundRect", itemWidth: 12, itemHeight: 4,
          textStyle: { color: theme.inkSecondary } }  // prettier-ignore
      : undefined,
    tooltip: {
      ...tooltipBase,
      trigger: "axis",
      axisPointer: { type: w.type === "line" ? "line" : "shadow", lineStyle: { color: theme.axis } },
    },
    xAxis: horizontal ? valAxis : catAxis,
    yAxis: horizontal ? catAxis : valAxis,
    series: series.map((s) => {
      const data = horizontal ? [...s.data].reverse() : s.data;
      if (w.type === "line") {
        return {
          name: s.name, type: "line", data, connectNulls: true, showSymbol: categories.length < 30,
          symbol: "circle", symbolSize: 8, lineStyle: { width: 2, cap: "round", join: "round" },
          itemStyle: { borderColor: theme.surface, borderWidth: 2 },
          emphasis: { focus: "series" },
        };  // prettier-ignore
      }
      return {
        name: s.name, type: "bar", data, stack: w.stacked ? "total" : undefined,
        barMaxWidth: 24, barGap: "8%",
        itemStyle: {
          borderRadius: w.stacked ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
          borderColor: theme.surface, borderWidth: w.stacked ? 2 : 0,
        },
        emphasis: { focus: "series" },
      };  // prettier-ignore
    }),
  };
}

export default function WidgetChart({ widget, result, height = 300 }: {
  widget: WidgetDef;
  result: QueryResult;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const scheme = useComputedColorScheme("light");
  const { t, i18n } = useTranslation();
  const theme = scheme === "dark" ? DARK : LIGHT;
  const label = useMemo(
    () => (key: string) => t(`dash.labels.${key}`, { defaultValue: key }),
    [t],
  );
  const option = useMemo(
    () => buildOption(widget, result, theme, i18n.language, label),
    [widget, result, theme, i18n.language, label],
  );

  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  // horizontal bars get one 22px band per row so every category label fits
  const h =
    widget.type === "bar" && widget.horizontal
      ? Math.max(height, result.rows.length * 22 + 50)
      : height;
  return <div ref={ref} style={{ width: "100%", height: h }} />;
}
