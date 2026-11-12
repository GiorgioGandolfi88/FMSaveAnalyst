import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconCode,
  IconDeviceFloppy,
  IconPlayerPlay,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import {
  Background,
  Controls,
  ReactFlow,
  applyNodeChanges,
  type Connection,
  type Edge,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { dataApi, type QueryResult, type SavedQuery, type Schema } from "../api";
import ExportMenu from "../components/ExportMenu";
import ResultGrid from "../components/ResultGrid";
import SqlEditor from "../components/SqlEditor";
import TableNode, { type TableNodeType } from "../components/TableNode";
import {
  buildSql,
  emptyModel,
  type Aggregate,
  type FilterOp,
  type QBJoin,
  type QueryModel,
} from "../lib/sqlBuilder";

const nodeTypes = { table: TableNode };
let counter = 0;
const uid = () => `${Date.now().toString(36)}${(counter++).toString(36)}`;

const AGGS: Aggregate[] = ["", "count", "count_distinct", "sum", "avg", "min", "max"];
const OPS: FilterOp[] = [
  "=", "!=", "<", "<=", ">", ">=", "contains", "starts", "ends", "between", "in", "null", "notnull",
];

interface Props {
  schema: Schema;
  initialSql: string | null;
  onInitialSqlUsed: () => void;
}

export default function QueryPage({ schema, initialSql, onInitialSqlUsed }: Props) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"builder" | "sql">("builder");
  const [model, setModel] = useState<QueryModel>(emptyModel);
  const [sql, setSql] = useState("SELECT name, age, club_name\nFROM players\nLIMIT 100");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ msg: string; ok: boolean } | null>(null);
  const [editingJoin, setEditingJoin] = useState<QBJoin | null>(null);
  const [saved, setSaved] = useState<SavedQuery[]>([]);
  const [saveName, setSaveName] = useState("");
  const [saveOpen, setSaveOpen] = useState(false);
  const [lastRunSql, setLastRunSql] = useState<string | null>(null);
  const [tableSearch, setTableSearch] = useState("");

  const objects = useMemo(() => new Map(schema.objects.map((o) => [o.name, o])), [schema]);
  const built = useMemo(() => buildSql(model), [model]);

  useEffect(() => {
    dataApi.savedQueries().then(setSaved).catch(() => setSaved([]));
  }, [schema.career]);

  useEffect(() => {
    if (initialSql) {
      setSql(initialSql);
      setMode("sql");
      onInitialSqlUsed();
    }
  }, [initialSql, onInitialSqlUsed]);

  // ------------------------------------------------------------ model edits

  const update = (fn: (m: QueryModel) => QueryModel) => setModel((m) => fn(m));

  const suggestJoin = (m: QueryModel, alias: string, table: string): QBJoin | null => {
    // prefer the most direct relation: "club_uid" rather than "loan_parent_club_uid"
    let best: QBJoin | null = null;
    let bestLen = Infinity;
    for (const other of m.tables) {
      for (const r of schema.relations) {
        let candidate: QBJoin | null = null;
        let length = Infinity;
        if (r.from_table === table && r.to_table === other.table) {
          candidate = { id: uid(), from: other.id, to: alias, fromColumn: r.to_column,
                        toColumn: r.from_column, type: "LEFT" };  // prettier-ignore
          length = r.from_column.length;
        } else if (r.from_table === other.table && r.to_table === table) {
          candidate = { id: uid(), from: other.id, to: alias, fromColumn: r.from_column,
                        toColumn: r.to_column, type: "LEFT" };  // prettier-ignore
          length = r.from_column.length;
        }
        if (candidate && length < bestLen) {
          best = candidate;
          bestLen = length;
        }
      }
    }
    return best;
  };

  const addTable = (table: string | null) => {
    if (!table) return;
    update((m) => {
      const n = m.tables.length;
      const used = new Set(m.tables.map((x) => x.id));
      let i = n + 1;
      while (used.has(`t${i}`)) i++;
      const alias = `t${i}`;
      const next = {
        ...m,
        tables: [...m.tables, { id: alias, table, x: 40 + n * 300, y: 30 + (n % 2) * 60 }],
      };
      const join = n ? suggestJoin(m, alias, table) : null;
      return join ? { ...next, joins: [...next.joins, join] } : next;
    });
  };

  const toggleColumn = useCallback((alias: string, column: string) => {
    setModel((m) => {
      const exists = m.columns.find((c) => c.alias === alias && c.column === column);
      return {
        ...m,
        columns: exists
          ? m.columns.filter((c) => c !== exists)
          : [...m.columns, { id: uid(), alias, column, agg: "", label: "" }],
      };
    });
  }, []);

  const removeTable = useCallback((alias: string) => {
    setModel((m) => ({
      ...m,
      tables: m.tables.filter((x) => x.id !== alias),
      columns: m.columns.filter((c) => c.alias !== alias),
      joins: m.joins.filter((j) => j.from !== alias && j.to !== alias),
      filters: m.filters.filter((f) => f.alias !== alias),
      sorts: m.sorts.filter((s) => s.alias !== alias),
    }));
  }, []);

  // React Flow keeps measured sizes on its nodes (needed to draw edges): keep its node objects
  // and refresh only position/data from the model.
  const [nodes, setNodes] = useState<TableNodeType[]>([]);
  useEffect(() => {
    setNodes((prev) =>
      model.tables.map((x) => {
        const old = prev.find((n) => n.id === x.id);
        return {
          ...(old ?? {}),
          id: x.id,
          type: "table" as const,
          position: old?.dragging ? old.position : { x: x.x, y: x.y },
          dragHandle: ".drag-handle",
          data: {
            alias: x.id,
            table: x.table,
            columns: objects.get(x.table)?.columns ?? [],
            selected: model.columns.filter((c) => c.alias === x.id).map((c) => c.column),
            onToggle: toggleColumn,
            onRemove: removeTable,
          },
        };
      }),
    );
  }, [model.tables, model.columns, objects, toggleColumn, removeTable]);

  const edges: Edge[] = model.joins.map((j) => ({
    id: j.id,
    source: j.from,
    target: j.to,
    label: `${j.fromColumn} = ${j.toColumn}${j.type === "LEFT" ? " (LEFT)" : ""}`,
    labelBgPadding: [4, 2],
    style: { strokeWidth: 2 },
  }));

  const onNodesChange = (changes: NodeChange<TableNodeType>[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
    const moved = new Map<string, { x: number; y: number }>();
    for (const c of changes) {
      if (c.type === "position" && c.position && !c.dragging) moved.set(c.id, c.position);
    }
    if (moved.size) {
      update((m) => ({
        ...m,
        tables: m.tables.map((x) => {
          const pos = moved.get(x.id);
          return pos ? { ...x, x: pos.x, y: pos.y } : x;
        }),
      }));
    }
  };

  const onConnect = (c: Connection) => {
    if (!c.source || !c.target || c.source === c.target) return;
    const from = model.tables.find((x) => x.id === c.source);
    const to = model.tables.find((x) => x.id === c.target);
    if (!from || !to) return;
    const others = { ...model, tables: [from] };
    const suggested = suggestJoin(others, to.id, to.table);
    const join: QBJoin = suggested ?? {
      id: uid(), from: from.id, to: to.id, type: "LEFT",
      fromColumn: objects.get(from.table)?.columns[0]?.name ?? "",
      toColumn: objects.get(to.table)?.columns[0]?.name ?? "",
    };  // prettier-ignore
    update((m) => ({ ...m, joins: [...m.joins, join] }));
    if (!suggested) setEditingJoin(join);
  };

  // ------------------------------------------------------------ run / save

  const run = async (text: string) => {
    if (!text.trim()) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await dataApi.query(text));
      setLastRunSql(text);
    } catch (e) {
      setError(String(e));
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  const currentSql = mode === "builder" ? built.sql : sql;

  const persist = async (list: SavedQuery[]) => {
    try {
      setSaved(await dataApi.saveQueries(list));
    } catch (e) {
      setError(String(e));
    }
  };

  const saveCurrent = async () => {
    const name = saveName.trim();
    if (!name) return;
    const entry: SavedQuery = {
      name,
      sql: currentSql,
      model: mode === "builder" ? (model as unknown as Record<string, unknown>) : null,
    };
    await persist([...saved.filter((s) => s.name !== name), entry]);
    setSaveOpen(false);
    setNotice({ msg: t("query.savedOk", { name }), ok: true });
  };

  const load = (name: string | null) => {
    const q = saved.find((s) => s.name === name);
    if (!q) return;
    if (q.model) {
      setModel(q.model as unknown as QueryModel);
      setMode("builder");
    } else {
      setSql(q.sql);
      setMode("sql");
    }
    setSaveName(q.name);
  };

  const columnOptions = model.tables.flatMap((x) =>
    (objects.get(x.table)?.columns ?? [])
      .filter((c) => !c.internal)
      .map((c) => ({ value: `${x.id}|${c.name}`, label: `${x.id}.${c.name}` })),
  );
  const splitRef = (v: string | null) => {
    const [alias, column] = (v ?? "|").split("|");
    return { alias, column };
  };

  // ------------------------------------------------------------ render

  const builder = (
    <Stack gap="sm">
      <Group gap="xs">
        <Select
          w={320}
          searchable
          placeholder={t("query.addTable")}
          leftSection={<IconPlus size={14} />}
          value={null}
          searchValue={tableSearch}
          onSearchChange={setTableSearch}
          selectFirstOptionOnChange
          onChange={(v) => {
            addTable(v);
            setTableSearch("");
          }}
          data={["data", "derived", "reference", "history"].map((g) => ({
            group: t(`explore.groups.${g}`),
            items: schema.objects.filter((o) => o.group === g).map((o) => o.name),
          }))}
        />
        <Text size="xs" c="dimmed">
          {t("query.builderHint")}
        </Text>
      </Group>
      <Paper withBorder h={380}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          onEdgeClick={(_, e) => setEditingJoin(model.joins.find((j) => j.id === e.id) ?? null)}
          fitView={false}
          minZoom={0.3}
          deleteKeyCode={null}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </Paper>

      <Tabs defaultValue="columns" variant="outline">
        <Tabs.List>
          <Tabs.Tab value="columns">
            {t("query.columns")} <Badge size="xs" variant="light">{model.columns.length}</Badge>
          </Tabs.Tab>
          <Tabs.Tab value="filters">
            {t("query.filters")} <Badge size="xs" variant="light">{model.filters.length}</Badge>
          </Tabs.Tab>
          <Tabs.Tab value="sort">
            {t("query.sort")} <Badge size="xs" variant="light">{model.sorts.length}</Badge>
          </Tabs.Tab>
          <Tabs.Tab value="options">{t("query.options")}</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="columns" pt="xs">
          {model.columns.length === 0 ? (
            <Text size="sm" c="dimmed">{t("query.noColumns")}</Text>
          ) : (
            <Table withRowBorders={false} verticalSpacing={2}>
              <Table.Tbody>
                {model.columns.map((c) => (
                  <Table.Tr key={c.id}>
                    <Table.Td w={260}><Text size="sm">{c.alias}.{c.column}</Text></Table.Td>
                    <Table.Td w={170}>
                      <Select size="xs" allowDeselect={false} value={c.agg}
                        data={AGGS.map((a) => ({ value: a, label: t(`query.agg.${a || "none"}`) }))}
                        onChange={(v) => update((m) => ({ ...m, columns: m.columns.map((x) =>
                          x.id === c.id ? { ...x, agg: (v ?? "") as Aggregate } : x) }))} />
                    </Table.Td>
                    <Table.Td>
                      <TextInput size="xs" placeholder={t("query.label")} value={c.label}
                        onChange={(e) => { const label = e.currentTarget.value;
                          update((m) => ({ ...m, columns: m.columns.map((x) =>
                            x.id === c.id ? { ...x, label } : x) })); }} />
                    </Table.Td>
                    <Table.Td w={40}>
                      <ActionIcon variant="subtle" color="gray" onClick={() => toggleColumn(c.alias, c.column)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="filters" pt="xs">
          <Stack gap={4}>
            {model.filters.map((f) => (
              <Group key={f.id} gap="xs" wrap="nowrap">
                <Select size="xs" w={260} searchable data={columnOptions}
                  value={f.column ? `${f.alias}|${f.column}` : null}
                  onChange={(v) => update((m) => ({ ...m, filters: m.filters.map((x) =>
                    x.id === f.id ? { ...x, ...splitRef(v) } : x) }))} />
                <Select size="xs" w={150} allowDeselect={false} value={f.op}
                  data={OPS.map((o) => ({ value: o, label: t(`query.ops.${o}`) }))}
                  onChange={(v) => update((m) => ({ ...m, filters: m.filters.map((x) =>
                    x.id === f.id ? { ...x, op: (v ?? "=") as FilterOp } : x) }))} />
                {f.op !== "null" && f.op !== "notnull" && (
                  <TextInput size="xs" w={180} value={f.value}
                    placeholder={f.op === "in" ? "a, b, c" : ""}
                    onChange={(e) => { const value = e.currentTarget.value;
                      update((m) => ({ ...m, filters: m.filters.map((x) =>
                        x.id === f.id ? { ...x, value } : x) })); }} />
                )}
                {f.op === "between" && (
                  <TextInput size="xs" w={140} value={f.value2}
                    onChange={(e) => { const value2 = e.currentTarget.value;
                      update((m) => ({ ...m, filters: m.filters.map((x) =>
                        x.id === f.id ? { ...x, value2 } : x) })); }} />
                )}
                <ActionIcon variant="subtle" color="gray"
                  onClick={() => update((m) => ({ ...m, filters: m.filters.filter((x) => x.id !== f.id) }))}>
                  <IconTrash size={14} />
                </ActionIcon>
              </Group>
            ))}
            <Button size="xs" variant="light" w="fit-content" leftSection={<IconPlus size={14} />}
              disabled={!model.tables.length}
              onClick={() => update((m) => ({ ...m, filters: [...m.filters, { id: uid(),
                alias: m.tables[0].id, column: "", op: "=", value: "", value2: "" }] }))}>
              {t("query.addFilter")}
            </Button>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="sort" pt="xs">
          <Stack gap={4}>
            {model.sorts.map((s) => (
              <Group key={s.id} gap="xs">
                <Select size="xs" w={260} searchable data={columnOptions}
                  value={s.column ? `${s.alias}|${s.column}` : null}
                  onChange={(v) => update((m) => ({ ...m, sorts: m.sorts.map((x) =>
                    x.id === s.id ? { ...x, ...splitRef(v) } : x) }))} />
                <SegmentedControl size="xs" value={s.dir}
                  data={[{ value: "ASC", label: t("query.asc") }, { value: "DESC", label: t("query.desc") }]}
                  onChange={(v) => update((m) => ({ ...m, sorts: m.sorts.map((x) =>
                    x.id === s.id ? { ...x, dir: v as "ASC" | "DESC" } : x) }))} />
                <ActionIcon variant="subtle" color="gray"
                  onClick={() => update((m) => ({ ...m, sorts: m.sorts.filter((x) => x.id !== s.id) }))}>
                  <IconTrash size={14} />
                </ActionIcon>
              </Group>
            ))}
            <Button size="xs" variant="light" w="fit-content" leftSection={<IconPlus size={14} />}
              disabled={!model.tables.length}
              onClick={() => update((m) => ({ ...m, sorts: [...m.sorts, { id: uid(),
                alias: m.tables[0].id, column: "", dir: "DESC" }] }))}>
              {t("query.addSort")}
            </Button>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="options" pt="xs">
          <Group>
            <NumberInput size="xs" w={160} label={t("query.limit")} min={1} max={200000}
              value={model.limit ?? ""} onChange={(v) =>
                update((m) => ({ ...m, limit: typeof v === "number" ? v : null }))} />
            <Switch mt="md" label={t("query.distinct")} checked={model.distinct}
              onChange={(e) => { const distinct = e.currentTarget.checked;
                update((m) => ({ ...m, distinct })); }} />
            <Button mt="md" size="xs" variant="subtle" color="red"
              onClick={() => setModel(emptyModel())}>{t("query.clear")}</Button>
          </Group>
        </Tabs.Panel>
      </Tabs>

      {built.warnings.map((w) => (
        <Text key={w} size="xs" c="orange">{t(w)}</Text>
      ))}
      <SqlEditor value={built.sql} readOnly height={150} />
    </Stack>
  );

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Group gap="sm">
          <Title order={2}>{t("nav.query")}</Title>
          <SegmentedControl
            value={mode}
            onChange={(v) => setMode(v as "builder" | "sql")}
            data={[
              { value: "builder", label: t("query.modeBuilder") },
              { value: "sql", label: t("query.modeSql") },
            ]}
          />
        </Group>
        <Group gap="xs">
          <Select
            w={220}
            size="sm"
            placeholder={t("query.savedQueries")}
            data={saved.map((s) => s.name)}
            value={null}
            onChange={load}
            searchable
            nothingFoundMessage="—"
          />
          {mode === "builder" && (
            <Button variant="default" leftSection={<IconCode size={16} />}
              disabled={!built.sql} onClick={() => { setSql(built.sql); setMode("sql"); }}>
              {t("query.editAsSql")}
            </Button>
          )}
          <Button variant="default" leftSection={<IconDeviceFloppy size={16} />}
            disabled={!currentSql.trim()} onClick={() => setSaveOpen(true)}>
            {t("query.save")}
          </Button>
          <Button leftSection={<IconPlayerPlay size={16} />} loading={running}
            disabled={!currentSql.trim()} onClick={() => run(currentSql)}>
            {t("query.run")}
          </Button>
        </Group>
      </Group>

      {mode === "builder" ? builder : (
        <Stack gap={4}>
          <SqlEditor value={sql} onChange={setSql} onRun={() => run(sql)} schema={schema} height={260} />
          <Text size="xs" c="dimmed">{t("query.sqlHint")}</Text>
        </Stack>
      )}

      {error && <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      {notice && (
        <Alert color={notice.ok ? "teal" : "red"} withCloseButton onClose={() => setNotice(null)} py={6}>
          {notice.msg}
        </Alert>
      )}

      {result && (
        <Stack gap={4}>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {t("query.resultInfo", { count: result.row_count, ms: result.elapsed_ms })}
              {result.truncated && ` · ${t("query.truncated")}`}
              {result.masked.length > 0 && ` · 🔒 ${result.masked.join(", ")}`}
            </Text>
            <ExportMenu source={lastRunSql ? { sql: lastRunSql } : null} baseName="query"
              onResult={(msg, ok) => setNotice({ msg, ok })} />
          </Group>
          <div style={{ height: 420 }}>
            <ResultGrid result={result} />
          </div>
        </Stack>
      )}

      <Modal opened={!!editingJoin} onClose={() => setEditingJoin(null)} title={t("query.join")}>
        {editingJoin && (() => {
          const j = model.joins.find((x) => x.id === editingJoin.id) ?? editingJoin;
          const fromT = model.tables.find((x) => x.id === j.from);
          const toT = model.tables.find((x) => x.id === j.to);
          const colsOf = (table?: string) =>
            (objects.get(table ?? "")?.columns ?? []).map((c) => c.name);
          const setJ = (patch: Partial<QBJoin>) =>
            update((m) => ({ ...m, joins: m.joins.map((x) => (x.id === j.id ? { ...x, ...patch } : x)) }));
          return (
            <Stack>
              <SegmentedControl value={j.type} onChange={(v) => setJ({ type: v as "INNER" | "LEFT" })}
                data={[{ value: "LEFT", label: t("query.leftJoin") }, { value: "INNER", label: t("query.innerJoin") }]} />
              <Group grow>
                <Select label={`${fromT?.table} (${j.from})`} searchable data={colsOf(fromT?.table)}
                  value={j.fromColumn} onChange={(v) => v && setJ({ fromColumn: v })} />
                <Select label={`${toT?.table} (${j.to})`} searchable data={colsOf(toT?.table)}
                  value={j.toColumn} onChange={(v) => v && setJ({ toColumn: v })} />
              </Group>
              <Group justify="space-between">
                <Button color="red" variant="subtle" onClick={() => {
                  update((m) => ({ ...m, joins: m.joins.filter((x) => x.id !== j.id) }));
                  setEditingJoin(null); }}>
                  {t("query.removeJoin")}
                </Button>
                <Button onClick={() => setEditingJoin(null)}>{t("careers.close")}</Button>
              </Group>
            </Stack>
          );
        })()}
      </Modal>

      <Modal opened={saveOpen} onClose={() => setSaveOpen(false)} title={t("query.save")}>
        <Stack>
          <TextInput label={t("query.saveName")} value={saveName} data-autofocus
            onChange={(e) => setSaveName(e.currentTarget.value)} />
          {saved.length > 0 && (
            <Stack gap={2}>
              <Text size="xs" c="dimmed">{t("query.savedQueries")}</Text>
              {saved.map((s) => (
                <Group key={s.name} justify="space-between">
                  <Text size="sm">{s.name}</Text>
                  <ActionIcon size="sm" variant="subtle" color="red"
                    onClick={() => persist(saved.filter((x) => x.name !== s.name))}>
                    <IconTrash size={12} />
                  </ActionIcon>
                </Group>
              ))}
            </Stack>
          )}
          <Group justify="flex-end">
            <Button disabled={!saveName.trim()} onClick={saveCurrent}>{t("query.save")}</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
