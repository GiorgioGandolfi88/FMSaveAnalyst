import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Loader,
  Menu,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconChartBar,
  IconDots,
  IconFileZip,
  IconTable,
} from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  dashboardsApi,
  exportDashboard,
  exportData,
  localized,
  type Dashboard,
  type DashboardParams,
  type DashboardSummary,
  type DashboardWidget,
  type ExportFormat,
  type QueryResult,
  type WidgetData,
} from "../api";
import ResultGrid from "../components/ResultGrid";
import WidgetChart from "../components/WidgetChart";
import { compact, full } from "../lib/vizTheme";

interface Props {
  onOpenInQuery: (sql: string) => void;
}

type ParamValues = Record<string, string | number | null>;

function inlineParams(sql: string, values: ParamValues & { today?: string | null }): string {
  return sql.replace(/:(club|competition|season|today)\b/g, (_, name: string) => {
    const v = values[name];
    if (v === null || v === undefined) return "NULL";
    return typeof v === "number" ? String(v) : `'${String(v).replace(/'/g, "''")}'`;
  });
}

function KpiTile({ w, data, lang }: { w: DashboardWidget; data: QueryResult; lang: string }) {
  const raw = data.rows[0]?.[0];
  let value = "—";
  if (raw !== null && raw !== undefined) {
    if (typeof raw === "number") {
      value = w.format === "money" ? compact(raw, lang) : full(raw, lang);
    } else value = String(raw);
  }
  const masked = data.masked.length > 0 && (raw === null || raw === undefined);
  return (
    <Stack gap={2}>
      <Text size="sm" c="dimmed">{localized(w.title, lang)}</Text>
      <Text fz={28} fw={600} lh={1.2}>{masked ? "🔒" : value}</Text>
    </Stack>
  );
}

function WidgetCard({ w, data, lang, values, onOpenInQuery, onNotice }: {
  w: DashboardWidget;
  data: WidgetData | undefined;
  lang: string;
  values: ParamValues & { today?: string | null };
  onOpenInQuery: (sql: string) => void;
  onNotice: (msg: string, ok: boolean) => void;
}) {
  const { t } = useTranslation();
  const [view, setView] = useState<"chart" | "table">(w.type === "table" ? "table" : "chart");
  const sql = inlineParams(w.sql, values);

  const doExport = async (format: ExportFormat) => {
    try {
      const where = await exportData({ sql: w.sql, params: values }, format, `${w.id}`);
      if (where) onNotice(t("export.done", { path: where }), true);
    } catch (e) {
      onNotice(`${t("export.failed")}: ${String(e)}`, false);
    }
  };

  let body;
  if (!data) body = <Loader size="sm" />;
  else if ("error" in data) body = <Alert color="red" py={4}>{data.error}</Alert>;
  else if (w.type === "kpi") body = <KpiTile w={w} data={data} lang={lang} />;
  else if (data.row_count === 0) body = <Text size="sm" c="dimmed">{t("dash.noData")}</Text>;
  else if (view === "table" || w.type === "table")
    body = <div style={{ height: w.type === "table" ? 360 : 300 }}><ResultGrid result={data} /></div>;
  else body = <WidgetChart widget={w} result={data} />;

  return (
    <Paper withBorder p="sm" h="100%">
      {w.type !== "kpi" && (
        <Group justify="space-between" mb={6} wrap="nowrap">
          <Text fw={600} size="sm">{localized(w.title, lang)}</Text>
          <Group gap={4} wrap="nowrap">
            {w.type !== "table" && (
              <SegmentedControl size="xs" value={view} onChange={(v) => setView(v as "chart" | "table")}
                data={[
                  { value: "chart", label: <IconChartBar size={14} aria-label={t("dash.chart")} /> },
                  { value: "table", label: <IconTable size={14} aria-label={t("dash.table")} /> },
                ]} />
            )}
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="subtle" color="gray" aria-label={t("dash.more")}>
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={() => doExport("csv_excel")}>{t("export.csvExcel")}</Menu.Item>
                <Menu.Item onClick={() => doExport("csv")}>{t("export.csv")}</Menu.Item>
                <Menu.Item onClick={() => doExport("json")}>{t("export.json")}</Menu.Item>
                <Menu.Divider />
                <Menu.Item onClick={() => onOpenInQuery(sql)}>{t("explore.openInQuery")}</Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      )}
      {body}
    </Paper>
  );
}

export default function DashboardsPage({ onOpenInQuery }: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [list, setList] = useState<DashboardSummary[] | null>(null);
  const [params, setParams] = useState<DashboardParams | null>(null);
  const [current, setCurrent] = useState<Dashboard | null>(null);
  const [values, setValues] = useState<ParamValues>({});
  const [data, setData] = useState<Record<string, WidgetData>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    Promise.all([dashboardsApi.list(), dashboardsApi.params()])
      .then(([l, p]) => {
        setList(l);
        setParams(p);
        setValues({ club: p.club.default, competition: p.competition.default, season: p.season.default });
      })
      .catch((e) => setError(String(e)));
  }, []);

  const fullValues = useMemo(() => ({ ...values, today: params?.today ?? null }), [values, params]);

  const load = useCallback(async (d: Dashboard, v: ParamValues) => {
    setLoading(true);
    setData({});
    try {
      const r = await dashboardsApi.data(d.id, v);
      setData(r.widgets);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const open = async (id: string) => {
    try {
      const d = await dashboardsApi.get(id);
      setCurrent(d);
      void load(d, values);
    } catch (e) {
      setError(String(e));
    }
  };

  const setParam = (name: string, value: string | null) => {
    const opts = params?.[name as "club"]?.options ?? [];
    const match = opts.find((o) => String(o.value) === value);
    const next = { ...values, [name]: match ? match.value : null };
    setValues(next);
    if (current) void load(current, next);
  };

  const zip = async (format: ExportFormat) => {
    if (!current) return;
    try {
      const where = await exportDashboard(current.id, values, format);
      if (where) setNotice({ msg: t("export.done", { path: where }), ok: true });
    } catch (e) {
      setNotice({ msg: `${t("export.failed")}: ${String(e)}`, ok: false });
    }
  };

  if (error) return <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>;
  if (!list || !params) return <Loader />;

  if (!current) {
    return (
      <Stack>
        <Title order={2}>{t("nav.dashboards")}</Title>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {list.map((d) => (
            <Card key={d.id} withBorder padding="md" style={{ cursor: "pointer" }} onClick={() => open(d.id)}>
              <Group justify="space-between" mb={4}>
                <Text fw={600}>{localized(d.title, lang)}</Text>
                {d.source === "user" && <Badge variant="light">{t("dash.custom")}</Badge>}
              </Group>
              <Text size="sm" c="dimmed">{localized(d.description, lang)}</Text>
              <Group gap={4} mt="sm">
                {d.params.map((p) => <Badge key={p} variant="outline" color="gray" size="xs">{t(`dash.params.${p}`)}</Badge>)}
              </Group>
            </Card>
          ))}
        </SimpleGrid>
        <Text size="xs" c="dimmed">{t("dash.customHint")}</Text>
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Group gap="xs">
          <Tooltip label={t("dash.back")}>
            <ActionIcon variant="default" onClick={() => { setCurrent(null); setData({}); }}>
              <IconArrowLeft size={16} />
            </ActionIcon>
          </Tooltip>
          <Title order={2}>{localized(current.title, lang)}</Title>
          {loading && <Loader size="xs" />}
        </Group>
        <Menu position="bottom-end" withinPortal>
          <Menu.Target>
            <Button variant="default" leftSection={<IconFileZip size={16} />}>{t("dash.exportAll")}</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={() => zip("csv_excel")}>{t("export.csvExcel")}</Menu.Item>
            <Menu.Item onClick={() => zip("csv")}>{t("export.csv")}</Menu.Item>
            <Menu.Item onClick={() => zip("json")}>{t("export.json")}</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
      <Text size="sm" c="dimmed">{localized(current.description, lang)}</Text>

      {current.params.length > 0 && (
        <Group gap="sm">
          {current.params.map((p) => {
            const opts = params[p as "club"].options;
            return (
              <Select key={p} w={p === "season" ? 140 : 320} label={t(`dash.params.${p}`)} searchable
                allowDeselect={false} limit={200}
                value={values[p] === null || values[p] === undefined ? null : String(values[p])}
                data={opts.map((o) => ({ value: String(o.value), label: o.label }))}
                onChange={(v) => setParam(p, v)} nothingFoundMessage="—" />
            );
          })}
        </Group>
      )}
      {notice && (
        <Alert color={notice.ok ? "teal" : "red"} withCloseButton onClose={() => setNotice(null)} py={6}>
          {notice.msg}
        </Alert>
      )}

      <Grid gap="sm">
        {current.widgets.map((w) => (
          <Grid.Col key={`${current.id}-${w.id}`} span={{ base: w.type === "kpi" ? 6 : 12, md: w.span ?? 12 }}>
            <WidgetCard w={w} data={loading ? undefined : data[w.id]} lang={lang} values={fullValues}
              onOpenInQuery={onOpenInQuery} onNotice={(msg, ok) => setNotice({ msg, ok })} />
          </Grid.Col>
        ))}
      </Grid>
    </Stack>
  );
}
