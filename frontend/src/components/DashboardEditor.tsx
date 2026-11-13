import {
  ActionIcon,
  Alert,
  Button,
  Group,
  MultiSelect,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconArrowDown,
  IconArrowUp,
  IconCopy,
  IconPlayerPlay,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  dashboardsApi,
  type Dashboard,
  type DashboardInput,
  type DashboardWidget,
  type Localized,
  type WidgetData,
} from "../api";
import ResultGrid from "./ResultGrid";
import SqlEditor from "./SqlEditor";

const PARAMS = ["club", "competition", "season", "nation", "league"];
const TYPES: DashboardWidget["type"][] = ["kpi", "table", "bar", "line", "scatter"];
const SPANS = ["3", "4", "6", "8", "12"];
const FORMATS = ["int", "decimal", "money", "text"];

export function blankDashboard(): Dashboard {
  return {
    id: "",
    title: { it: "", en: "" },
    description: { it: "", en: "" },
    params: [],
    inputs: [],
    source: "user",
    widgets: [blankWidget(1)],
  };
}

function blankWidget(n: number): DashboardWidget {
  return {
    id: `widget${n}`,
    type: "table",
    span: 12,
    title: { it: "", en: "" },
    sql: "SELECT name, age, club_name FROM players ORDER BY ability_current DESC LIMIT 20",
  };
}

function slug(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

function LocalizedFields({ label, value, onChange, multiline }: {
  label: string;
  value: Localized;
  onChange: (v: Localized) => void;
  multiline?: boolean;
}) {
  const Field = multiline ? Textarea : TextInput;
  return (
    <SimpleGrid cols={2} spacing="xs">
      <Field label={`${label} (IT)`} value={value.it ?? ""} autosize={multiline || undefined}
        onChange={(e) => onChange({ ...value, it: e.currentTarget.value })} />
      <Field label={`${label} (EN)`} value={value.en ?? ""} autosize={multiline || undefined}
        onChange={(e) => onChange({ ...value, en: e.currentTarget.value })} />
    </SimpleGrid>
  );
}

function WidgetEditor({ w, index, count, result, onChange, onMove, onDuplicate, onDelete }: {
  w: DashboardWidget;
  index: number;
  count: number;
  result: WidgetData | undefined;
  onChange: (w: DashboardWidget) => void;
  onMove: (delta: number) => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const set = (patch: Partial<DashboardWidget>) => onChange({ ...w, ...patch });
  const chart = w.type === "bar" || w.type === "line" || w.type === "scatter";
  const y = Array.isArray(w.y) ? w.y.join(", ") : (w.y ?? "");

  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={600}>
            {t("dashEdit.widget")} {index + 1}
          </Text>
          <Group gap={4}>
            <ActionIcon variant="subtle" disabled={index === 0} onClick={() => onMove(-1)}
              aria-label={t("dashEdit.up")}><IconArrowUp size={16} /></ActionIcon>
            <ActionIcon variant="subtle" disabled={index === count - 1} onClick={() => onMove(1)}
              aria-label={t("dashEdit.down")}><IconArrowDown size={16} /></ActionIcon>
            <Tooltip label={t("dashEdit.duplicate")}>
              <ActionIcon variant="subtle" onClick={onDuplicate}><IconCopy size={16} /></ActionIcon>
            </Tooltip>
            <Tooltip label={t("dashEdit.removeWidget")}>
              <ActionIcon variant="subtle" color="red" disabled={count === 1} onClick={onDelete}>
                <IconTrash size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
        <Group grow align="flex-end">
          <TextInput label={t("dashEdit.widgetId")} value={w.id}
            onChange={(e) => set({ id: e.currentTarget.value.replace(/[^A-Za-z0-9_-]/g, "") })} />
          <Select label={t("dashEdit.type")} value={w.type} allowDeselect={false}
            data={TYPES.map((x) => ({ value: x, label: t(`dashEdit.types.${x}`) }))}
            onChange={(v) => set({ type: (v ?? "table") as DashboardWidget["type"] })} />
          <Select label={t("dashEdit.span")} value={String(w.span ?? 12)} allowDeselect={false}
            data={SPANS} onChange={(v) => set({ span: Number(v ?? 12) })} />
          {w.type === "kpi" && (
            <Select label={t("dashEdit.format")} value={w.format ?? "int"} allowDeselect={false}
              data={FORMATS.map((x) => ({ value: x, label: t(`dashEdit.formats.${x}`) }))}
              onChange={(v) => set({ format: (v ?? "int") as DashboardWidget["format"] })} />
          )}
        </Group>
        <LocalizedFields label={t("dashEdit.widgetTitle")} value={w.title}
          onChange={(title) => set({ title })} />
        {chart && (
          <Group grow align="flex-end">
            <TextInput label={t("dashEdit.x")} value={w.x ?? ""}
              onChange={(e) => set({ x: e.currentTarget.value || undefined })} />
            <TextInput label={t("dashEdit.y")} value={y} description={t("dashEdit.yHint")}
              onChange={(e) => {
                const parts = e.currentTarget.value.split(",").map((s) => s.trim()).filter(Boolean);
                set({ y: parts.length > 1 ? parts : parts[0] });
              }} />
            <TextInput label={t("dashEdit.series")} value={w.series ?? ""}
              onChange={(e) => set({ series: e.currentTarget.value || undefined })} />
          </Group>
        )}
        {chart && (
          <Group>
            {w.type === "bar" && (
              <>
                <Switch label={t("dashEdit.horizontal")} checked={!!w.horizontal}
                  onChange={(e) => set({ horizontal: e.currentTarget.checked || undefined })} />
                <Switch label={t("dashEdit.stacked")} checked={!!w.stacked}
                  onChange={(e) => set({ stacked: e.currentTarget.checked || undefined })} />
              </>
            )}
            <Switch label={t("dashEdit.invertY")} checked={!!w.invert_y}
              onChange={(e) => set({ invert_y: e.currentTarget.checked || undefined })} />
          </Group>
        )}
        <Text size="sm" fw={500}>SQL</Text>
        <SqlEditor value={w.sql} onChange={(sql) => set({ sql })} height={160} />
        {result && ("error" in result ? (
          <Alert color="red" py={4}>{result.error}</Alert>
        ) : (
          <Stack gap={2}>
            <Text size="xs" c="dimmed">
              {t("dashEdit.rows", { n: result.row_count, columns: result.columns.join(", ") })}
            </Text>
            <div style={{ height: 180 }}><ResultGrid result={result} /></div>
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}

interface Props {
  initial: Dashboard;
  /** the id the dashboard has on disk (null: new dashboard) */
  originalId: string | null;
  values: Record<string, unknown>;
  onSaved: (d: Dashboard) => void;
  onCancel: () => void;
}

export default function DashboardEditor({ initial, originalId, values, onSaved, onCancel }: Props) {
  const { t } = useTranslation();
  const [d, setD] = useState<Dashboard>(() => structuredClone(initial));
  const [mode, setMode] = useState<"form" | "json">("form");
  const [json, setJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [results, setResults] = useState<Record<string, WidgetData>>({});
  const [idTouched, setIdTouched] = useState(originalId !== null);

  const set = (patch: Partial<Dashboard>) => setD((x) => ({ ...x, ...patch }));
  const setWidget = (i: number, w: DashboardWidget) =>
    setD((x) => ({ ...x, widgets: x.widgets.map((y, j) => (j === i ? w : y)) }));
  const setInput = (i: number, patch: Partial<DashboardInput>) =>
    setD((x) => ({
      ...x,
      inputs: (x.inputs ?? []).map((y, j) => (j === i ? { ...y, ...patch } : y)),
    }));

  const clean = (x: Dashboard): Dashboard => {
    const out: Record<string, unknown> = { ...x };
    delete out.source;
    delete out.builtin;
    delete out.file;
    return out as unknown as Dashboard;
  };

  const switchMode = (next: "form" | "json") => {
    setError(null);
    if (next === "json") {
      setJson(JSON.stringify(clean(d), null, 1));
    } else {
      try {
        setD({ ...JSON.parse(json), source: "user" });
      } catch (e) {
        setError(`JSON: ${String(e)}`);
        return;
      }
    }
    setMode(next);
  };

  const current = (): Dashboard | null => {
    if (mode === "form") return d;
    try {
      return { ...JSON.parse(json), source: "user" };
    } catch (e) {
      setError(`JSON: ${String(e)}`);
      return null;
    }
  };

  const test = async () => {
    const x = current();
    if (!x) return;
    setTesting(true);
    setError(null);
    try {
      setResults((await dashboardsApi.preview(clean(x), values)).widgets);
    } catch (e) {
      setError(String(e));
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    const x = current();
    if (!x) return;
    setSaving(true);
    setError(null);
    try {
      onSaved(await dashboardsApi.save(clean(x), originalId));
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const move = (i: number, delta: number) =>
    setD((x) => {
      const w = [...x.widgets];
      [w[i], w[i + delta]] = [w[i + delta], w[i]];
      return { ...x, widgets: w };
    });

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Title order={2}>{originalId ? t("dashEdit.editTitle") : t("dashEdit.newTitle")}</Title>
        <Group gap="xs">
          <SegmentedControl size="xs" value={mode} onChange={(v) => switchMode(v as "form" | "json")}
            data={[{ value: "form", label: t("dashEdit.form") }, { value: "json", label: "JSON" }]} />
          <Button variant="default" leftSection={<IconPlayerPlay size={16} />} loading={testing}
            onClick={test}>{t("dashEdit.test")}</Button>
          <Button variant="default" onClick={onCancel}>{t("careers.cancel")}</Button>
          <Button loading={saving} onClick={save}>{t("dashEdit.save")}</Button>
        </Group>
      </Group>
      {initial.builtin && (
        <Alert variant="light">{t("dashEdit.builtinNote")}</Alert>
      )}
      {error && <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {mode === "json" ? (
        <Textarea value={json} onChange={(e) => setJson(e.currentTarget.value)} autosize minRows={24}
          styles={{ input: { fontFamily: "monospace", fontSize: 12 } }} />
      ) : (
        <>
          <Paper withBorder p="sm">
            <Stack gap="xs">
              <LocalizedFields label={t("dashEdit.title")} value={d.title}
                onChange={(title) => set({ title, ...(idTouched ? {} : { id: slug(title.it || title.en || "") }) })} />
              <LocalizedFields label={t("dashEdit.description")} value={d.description} multiline
                onChange={(description) => set({ description })} />
              <Group grow align="flex-end">
                <TextInput label={t("dashEdit.id")} description={t("dashEdit.idHint")} value={d.id}
                  onChange={(e) => {
                    setIdTouched(true);
                    set({ id: e.currentTarget.value.replace(/[^A-Za-z0-9_-]/g, "") });
                  }} />
                <NumberInput label={t("dashEdit.order")} value={(d as { order?: number }).order ?? 100}
                  onChange={(v) => set({ order: Number(v) || 100 } as Partial<Dashboard>)} />
                <MultiSelect label={t("dashEdit.params")} value={d.params}
                  description={t("dashEdit.paramsHint")}
                  data={PARAMS.map((p) => ({ value: p, label: `${t(`dash.params.${p}`)} (:${p})` }))}
                  onChange={(params) => set({ params })} />
              </Group>
            </Stack>
          </Paper>

          <Paper withBorder p="sm">
            <Stack gap="xs">
              <Group justify="space-between">
                <Text fw={600}>{t("dashEdit.inputs")}</Text>
                <Button size="xs" variant="light" leftSection={<IconPlus size={14} />}
                  onClick={() => set({ inputs: [...(d.inputs ?? []),
                    { id: `value${(d.inputs ?? []).length + 1}`, default: 0, label: { it: "", en: "" } }] })}>
                  {t("dashEdit.addInput")}
                </Button>
              </Group>
              <Text size="xs" c="dimmed">{t("dashEdit.inputsHint")}</Text>
              {(d.inputs ?? []).map((i, n) => (
                <Group key={n} align="flex-end" gap="xs" wrap="nowrap">
                  <TextInput w={130} label="id" value={i.id}
                    onChange={(e) => setInput(n, { id: e.currentTarget.value.replace(/\W/g, "") })} />
                  <TextInput label={`${t("dashEdit.label")} (IT)`} value={i.label.it ?? ""}
                    onChange={(e) => setInput(n, { label: { ...i.label, it: e.currentTarget.value } })} />
                  <TextInput label={`${t("dashEdit.label")} (EN)`} value={i.label.en ?? ""}
                    onChange={(e) => setInput(n, { label: { ...i.label, en: e.currentTarget.value } })} />
                  <NumberInput w={100} label={t("dashEdit.default")} value={i.default}
                    onChange={(v) => setInput(n, { default: Number(v) || 0 })} />
                  <NumberInput w={90} label="min" value={i.min ?? ""}
                    onChange={(v) => setInput(n, { min: v === "" ? undefined : Number(v) })} />
                  <NumberInput w={90} label="max" value={i.max ?? ""}
                    onChange={(v) => setInput(n, { max: v === "" ? undefined : Number(v) })} />
                  <ActionIcon color="red" variant="subtle" mb={4}
                    onClick={() => set({ inputs: (d.inputs ?? []).filter((_, j) => j !== n) })}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Group>
              ))}
            </Stack>
          </Paper>

          {d.widgets.map((w, i) => (
            <WidgetEditor key={i} w={w} index={i} count={d.widgets.length} result={results[w.id]}
              onChange={(x) => setWidget(i, x)} onMove={(delta) => move(i, delta)}
              onDuplicate={() => setD((x) => ({ ...x, widgets: [...x.widgets.slice(0, i + 1),
                { ...structuredClone(w), id: `${w.id}_copy` }, ...x.widgets.slice(i + 1)] }))}
              onDelete={() => setD((x) => ({ ...x, widgets: x.widgets.filter((_, j) => j !== i) }))} />
          ))}
          <Group>
            <Button variant="light" leftSection={<IconPlus size={16} />}
              onClick={() => set({ widgets: [...d.widgets, blankWidget(d.widgets.length + 1)] })}>
              {t("dashEdit.addWidget")}
            </Button>
          </Group>
        </>
      )}
    </Stack>
  );
}
