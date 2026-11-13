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
  Modal,
  NumberInput,
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
  IconCopy,
  IconDots,
  IconFileZip,
  IconPencil,
  IconPlus,
  IconRestore,
  IconTable,
  IconTrash,
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
  type Localized,
  type ExportFormat,
  type QueryResult,
  type WidgetData,
} from "../api";
import DashboardEditor, { blankDashboard } from "../components/DashboardEditor";
import ResultGrid from "../components/ResultGrid";
import WidgetChart from "../components/WidgetChart";
import { compact, full } from "../lib/vizTheme";

interface Props {
  onOpenInQuery: (sql: string) => void;
}

type ParamValues = Record<string, string | number | null>;

function inlineParams(sql: string, values: ParamValues & { today?: string | null }): string {
  return sql.replace(/(?<![:\w]):([a-z_][a-z0-9_]*)\b/g, (whole, name: string) => {
    if (!(name in values)) return whole;
    const v = values[name];
    if (v === null || v === undefined) return "NULL";
    return typeof v === "number" ? String(v) : `'${String(v).replace(/'/g, "''")}'`;
  });
}

/** Titles can show input values: "Under {max_age}". */
function fillTitle(text: string, values: ParamValues): string {
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    values[name] === null || values[name] === undefined ? whole : String(values[name]));
}

function inputDefaults(d: Dashboard): ParamValues {
  return Object.fromEntries((d.inputs ?? []).map((i) => [i.id, i.default]));
}

function KpiTile({ w, data, lang, values }: {
  w: DashboardWidget; data: QueryResult; lang: string; values: ParamValues;
}) {
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
      <Text size="sm" c="dimmed">{fillTitle(localized(w.title, lang), values)}</Text>
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
  else if (w.type === "kpi") body = <KpiTile w={w} data={data} lang={lang} values={values} />;
  else if (data.row_count === 0) body = <Text size="sm" c="dimmed">{t("dash.noData")}</Text>;
  else if (view === "table" || w.type === "table")
    body = <div style={{ height: w.type === "table" ? 360 : 300 }}><ResultGrid result={data} /></div>;
  else body = <WidgetChart widget={w} result={data} />;

  return (
    <Paper withBorder p="sm" h="100%">
      {w.type !== "kpi" && (
        <Group justify="space-between" mb={6} wrap="nowrap">
          <Text fw={600} size="sm">{fillTitle(localized(w.title, lang), values)}</Text>
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
  const [editing, setEditing] = useState<{ d: Dashboard; originalId: string | null } | null>(null);
  const [hidden, setHidden] = useState<{ id: string; title: Localized }[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<DashboardSummary | null>(null);

  const reloadList = useCallback(() => {
    dashboardsApi.list().then(setList).catch((e) => setError(String(e)));
    dashboardsApi.hidden().then(setHidden).catch(() => setHidden([]));
  }, []);

  useEffect(() => {
    dashboardsApi.hidden().then(setHidden).catch(() => setHidden([]));
    Promise.all([dashboardsApi.list(), dashboardsApi.params()])
      .then(([l, p]) => {
        setList(l);
        setParams(p);
        setValues({
          club: p.club.default, competition: p.competition.default, season: p.season.default,
          nation: null, league: null,
        });
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
      const next = { ...values, ...inputDefaults(d) };
      setCurrent(d);
      setValues(next);
      void load(d, next);
    } catch (e) {
      setError(String(e));
    }
  };

  const usesParam = (name: string) => !!current && current.params.includes(name);

  const setParam = (name: string, value: string | null) => {
    const opts = params?.[name as "club"]?.options ?? [];
    const match = opts.find((o) => String(o.value) === value);
    const next = { ...values, [name]: match ? match.value : null };
    setValues(next);
    // on dashboards that do not filter on them, nation and league only narrow the club list
    if (current && usesParam(name)) void load(current, next);
  };

  const setInput = (name: string, value: string | number) => {
    setValues((v) => ({ ...v, [name]: typeof value === "number" ? value : null }));
  };
  const applyInputs = () => { if (current) void load(current, values); };
  const resetInputs = () => {
    if (!current) return;
    const next = { ...values, ...inputDefaults(current) };
    setValues(next);
    void load(current, next);
  };

  const clubOptions = useMemo(() => {
    const all = params?.club.options ?? [];
    const nation = values.nation;
    const league = values.league;
    return all.filter((o) =>
      (nation === null || nation === undefined || o.nation === nation) &&
      (league === null || league === undefined || (o.leagues ?? []).includes(Number(league))));
  }, [params, values.nation, values.league]);

  const zip = async (format: ExportFormat) => {
    if (!current) return;
    try {
      const where = await exportDashboard(current.id, values, format);
      if (where) setNotice({ msg: t("export.done", { path: where }), ok: true });
    } catch (e) {
      setNotice({ msg: `${t("export.failed")}: ${String(e)}`, ok: false });
    }
  };

  const edit = async (id: string, copy = false) => {
    try {
      const d = await dashboardsApi.get(id);
      if (copy) {
        const title = Object.fromEntries(
          Object.entries(d.title).map(([k, v]) => [k, `${v} (${t("dashEdit.copySuffix")})`]),
        );
        setEditing({ d: { ...d, id: `${d.id}_copy`, title, source: "user", builtin: false }, originalId: null });
      } else {
        setEditing({ d, originalId: d.id });
      }
    } catch (e) {
      setError(String(e));
    }
  };
  const remove = async (d: DashboardSummary) => {
    setConfirmDelete(null);
    try {
      await dashboardsApi.remove(d.id);
      if (current?.id === d.id) setCurrent(null);
      reloadList();
    } catch (e) {
      setError(String(e));
    }
  };
  const restore = async (id: string) => {
    try {
      const d = await dashboardsApi.restore(id);
      reloadList();
      if (current?.id === id) {
        setCurrent(d);
        void load(d, { ...values, ...inputDefaults(d) });
      }
    } catch (e) {
      setError(String(e));
    }
  };
  const saved = (d: Dashboard) => {
    setEditing(null);
    reloadList();
    void open(d.id);
  };

  if (error) return <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>;
  if (!list || !params) return <Loader />;

  if (editing) {
    return (
      <DashboardEditor initial={editing.d} originalId={editing.originalId}
        values={{ ...fullValues, ...inputDefaults(editing.d) }}
        onSaved={saved} onCancel={() => setEditing(null)} />
    );
  }

  const deleteModal = (
    <Modal opened={confirmDelete !== null} onClose={() => setConfirmDelete(null)}
      title={t("dashEdit.deleteTitle")}>
      <Stack>
        <Text>
          {confirmDelete?.source === "user" && !confirmDelete.builtin
            ? t("dashEdit.deleteUser", { name: localized(confirmDelete.title, lang) })
            : t("dashEdit.deleteBuiltin", { name: localized(confirmDelete?.title, lang) })}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setConfirmDelete(null)}>{t("careers.cancel")}</Button>
          <Button color="red" onClick={() => confirmDelete && remove(confirmDelete)}>
            {t("dashEdit.delete")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );

  const cardMenu = (d: DashboardSummary) => (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon variant="subtle" color="gray" onClick={(e) => e.stopPropagation()}
          aria-label={t("dash.more")}>
          <IconDots size={16} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
        <Menu.Item leftSection={<IconPencil size={14} />} onClick={() => edit(d.id)}>
          {t("dashEdit.edit")}
        </Menu.Item>
        <Menu.Item leftSection={<IconCopy size={14} />} onClick={() => edit(d.id, true)}>
          {t("dashEdit.duplicate")}
        </Menu.Item>
        {d.builtin && d.source === "user" && (
          <Menu.Item leftSection={<IconRestore size={14} />} onClick={() => restore(d.id)}>
            {t("dashEdit.restore")}
          </Menu.Item>
        )}
        <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={() => setConfirmDelete(d)}>
          {t("dashEdit.delete")}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );

  if (!current) {
    return (
      <Stack>
        <Group justify="space-between">
          <Title order={2}>{t("nav.dashboards")}</Title>
          <Button leftSection={<IconPlus size={16} />}
            onClick={() => setEditing({ d: blankDashboard(), originalId: null })}>
            {t("dashEdit.new")}
          </Button>
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {list.map((d) => (
            <Card key={d.id} withBorder padding="md" style={{ cursor: "pointer" }} onClick={() => open(d.id)}>
              <Group justify="space-between" mb={4} wrap="nowrap">
                <Text fw={600}>{localized(d.title, lang)}</Text>
                <Group gap={4} wrap="nowrap">
                  {d.source === "user" && (
                    <Badge variant="light">{d.builtin ? t("dashEdit.modified") : t("dash.custom")}</Badge>
                  )}
                  {cardMenu(d)}
                </Group>
              </Group>
              <Text size="sm" c="dimmed">{localized(d.description, lang)}</Text>
              <Group gap={4} mt="sm">
                {d.params.map((p) => <Badge key={p} variant="outline" color="gray" size="xs">{t(`dash.params.${p}`)}</Badge>)}
              </Group>
            </Card>
          ))}
        </SimpleGrid>
        {hidden.length > 0 && (
          <Paper withBorder p="sm">
            <Text fw={600} size="sm" mb={4}>{t("dashEdit.hiddenTitle")}</Text>
            <Group gap="xs">
              {hidden.map((h) => (
                <Button key={h.id} size="xs" variant="light" leftSection={<IconRestore size={14} />}
                  onClick={() => restore(h.id)}>
                  {localized(h.title, lang)}
                </Button>
              ))}
            </Group>
          </Paper>
        )}
        <Text size="xs" c="dimmed">{t("dash.customHint")}</Text>
        {deleteModal}
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
        <Group gap="xs">
        <Button variant="default" leftSection={<IconPencil size={16} />} onClick={() => edit(current.id)}>
          {t("dashEdit.edit")}
        </Button>
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
      </Group>
      <Text size="sm" c="dimmed">{localized(current.description, lang)}</Text>

      {(current.params.length > 0 || (current.inputs ?? []).length > 0) && (
        <Paper withBorder p="sm">
          <Group gap="sm" align="flex-end">
            {(usesParam("club") || usesParam("nation")) && (
              <Select w={260} label={usesParam("club") ? t("dash.params.clubNation") : t("dash.params.nation")}
                searchable clearable limit={300} placeholder={t("dash.all")}
                value={values.nation === null || values.nation === undefined ? null : String(values.nation)}
                data={params.nation.options.map((o) => ({ value: String(o.value), label: o.label }))}
                onChange={(v) => setParam("nation", v)} nothingFoundMessage="—" />
            )}
            {(usesParam("club") || usesParam("league")) && (
              <Select w={300} label={usesParam("club") ? t("dash.params.clubLeague") : t("dash.params.league")}
                searchable clearable limit={300} placeholder={t("dash.all")}
                value={values.league === null || values.league === undefined ? null : String(values.league)}
                data={params.league.options.map((o) => ({ value: String(o.value), label: o.label }))}
                onChange={(v) => setParam("league", v)} nothingFoundMessage="—" />
            )}
            {current.params.filter((p) => p !== "nation" && p !== "league").map((p) => {
              const opts = p === "club" ? clubOptions : params[p as "club"].options;
              return (
                <Select key={p} w={p === "season" ? 140 : 320} label={t(`dash.params.${p}`)} searchable
                  allowDeselect={false} limit={300}
                  value={values[p] === null || values[p] === undefined ? null : String(values[p])}
                  data={opts.map((o) => ({ value: String(o.value), label: o.label }))}
                  onChange={(v) => setParam(p, v)} nothingFoundMessage="—" />
              );
            })}
            {(current.inputs ?? []).map((i) => (
              <NumberInput key={i.id} w={170} label={localized(i.label, lang)} min={i.min} max={i.max}
                value={values[i.id] ?? i.default} onChange={(v) => setInput(i.id, v)}
                onBlur={applyInputs} onKeyDown={(e) => { if (e.key === "Enter") applyInputs(); }} />
            ))}
            {(current.inputs ?? []).length > 0 && (
              <Tooltip label={t("dash.resetInputs")}>
                <ActionIcon variant="default" size="lg" onClick={resetInputs} aria-label={t("dash.resetInputs")}>
                  <IconRestore size={16} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
          {(current.inputs ?? []).length > 0 && (
            <Text size="xs" c="dimmed" mt={6}>{t("dash.inputsHint")}</Text>
          )}
        </Paper>
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
