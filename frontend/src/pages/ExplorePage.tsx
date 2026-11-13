import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Collapse,
  Group,
  Loader,
  NavLink,
  Paper,
  Popover,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import {
  IconChevronDown,
  IconChevronRight,
  IconColumns,
  IconInfoCircle,
  IconSearch,
  IconSitemap,
} from "@tabler/icons-react";
import type { GridApi, IDatasource, IGetRowsParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { dataApi, type BrowseRequest, type Schema, type SchemaObject } from "../api";
import ExportMenu from "../components/ExportMenu";
import { columnDefs, gridLocale, toRecords, useGridTheme } from "../lib/grid";

export function sqlLiteral(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "number") return String(v);
  return `'${String(v).replace(/'/g, "''")}'`;
}

const GROUP_ORDER = ["people", "clubs", "nations", "competitions", "season_stats", "injuries", "managed", "save", "other", "derived", "reference", "history"] as const;

interface Props {
  schema: Schema;
  onOpenInQuery: (sql: string) => void;
}

export default function ExplorePage({ schema, onOpenInQuery }: Props) {
  const { t, i18n } = useTranslation();
  const theme = useGridTheme();
  const [search, setSearch] = useState("");
  const [table, setTable] = useState<SchemaObject | null>(
    schema.objects.find((o) => o.name === "Player") ?? schema.objects[0] ?? null,
  );
  const [hidden, setHidden] = useState<Record<string, Set<string>>>({});
  const [total, setTotal] = useState<number | null>(null);
  const [lastRequest, setLastRequest] = useState<BrowseRequest | null>(null);
  const [lastSql, setLastSql] = useState("");
  const [lastParams, setLastParams] = useState<unknown[]>([]);
  const [notice, setNotice] = useState<{ msg: string; ok: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // sections of the table list the user has closed (all open at first)
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const toggleGroup = (g: string) => {
    const next = new Set(closed);
    if (next.has(g)) next.delete(g);
    else next.add(g);
    setClosed(next);
  };
  const apiRef = useRef<GridApi | null>(null);

  const hiddenCols = useMemo(() => {
    if (!table) return new Set<string>();
    // internal columns are hidden until the user asks for them
    return hidden[table.name] ?? new Set(table.columns.filter((c) => c.internal).map((c) => c.name));
  }, [hidden, table]);

  const visibleColumns = useMemo(
    () => (table ? table.columns.filter((c) => !hiddenCols.has(c.name)) : []),
    [table, hiddenCols],
  );

  const defs = useMemo(
    () => columnDefs(visibleColumns, t("explore.masked")),
    [visibleColumns, t],
  );

  const datasource = useMemo<IDatasource | null>(() => {
    if (!table) return null;
    const columns = visibleColumns.map((c) => c.name);
    return {
      getRows: async (p: IGetRowsParams) => {
        const req: BrowseRequest = {
          table: table.name,
          columns,
          filter_model: p.filterModel as Record<string, unknown>,
          sort_model: p.sortModel.map((s) => ({ colId: s.colId, sort: s.sort })),
          start: p.startRow,
          end: p.endRow,
          count: p.startRow === 0,
        };
        try {
          const r = await dataApi.browse(req);
          setError(null);
          if (r.total !== null) setTotal(r.total);
          setLastRequest({ ...req, start: undefined, end: undefined, count: undefined });
          setLastSql(r.sql);
          setLastParams(r.params);
          const last = r.total ?? (r.rows.length < p.endRow - p.startRow ? p.startRow + r.rows.length : -1);
          p.successCallback(toRecords(r.columns, r.rows), last);
        } catch (e) {
          setError(String(e));
          p.failCallback();
        }
      },
    };
  }, [table, visibleColumns]);

  useEffect(() => setTotal(null), [table]);

  const toggleColumn = (name: string) => {
    if (!table) return;
    const next = new Set(hiddenCols);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setHidden({ ...hidden, [table.name]: next });
  };

  const openInQuery = useCallback(() => {
    // parameters are inlined so the SQL can be edited freely
    let i = 0;
    const sql = lastSql.replace(/\?/g, () => sqlLiteral(lastParams[i++]));
    onOpenInQuery(sql || `SELECT * FROM "${table?.name}"`);
  }, [lastSql, lastParams, onOpenInQuery, table]);

  const filtered = schema.objects.filter((o) =>
    o.name.toLowerCase().includes(search.trim().toLowerCase()),
  );

  return (
    <Group align="stretch" gap="md" wrap="nowrap" h="calc(100vh - 56px - 2 * var(--mantine-spacing-lg))">
      <Paper withBorder w={260} p="xs" style={{ display: "flex", flexDirection: "column" }}>
        <TextInput
          size="xs"
          leftSection={<IconSearch size={14} />}
          placeholder={t("explore.searchTables")}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          mb="xs"
        />
        <ScrollArea style={{ flex: 1 }}>
          {GROUP_ORDER.map((g) => {
            const items = filtered.filter((o) => o.group === g);
            if (!items.length) return null;
            // while searching every section shows its matches
            const open = search.trim() !== "" || !closed.has(g);
            return (
              <Stack gap={0} key={g} mb="xs">
                <Group gap={2} wrap="nowrap">
                  <UnstyledButton onClick={() => toggleGroup(g)} px={4} py={4} style={{ flex: 1 }}
                    aria-expanded={open}>
                    <Group gap={4} wrap="nowrap">
                      {open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                      <Text size="xs" fw={700} c="dimmed" tt="uppercase">
                        {t(`explore.groups.${g}`)}
                      </Text>
                      <Text size="xs" c="dimmed">({items.length})</Text>
                    </Group>
                  </UnstyledButton>
                  {(g === "history" || g === "reference" || g === "derived") && (
                    <Tooltip label={t(`explore.groupHelp.${g}`)} multiline w={320} withArrow position="right">
                      <IconInfoCircle size={14} color="var(--mantine-color-dimmed)" />
                    </Tooltip>
                  )}
                </Group>
                <Collapse expanded={open}>
                  {items.map((o) => (
                    <NavLink
                      key={o.name}
                      label={o.name}
                      active={table?.name === o.name}
                      onClick={() => setTable(o)}
                      py={3}
                      styles={{ label: { fontSize: 13 } }}
                    />
                  ))}
                </Collapse>
              </Stack>
            );
          })}
        </ScrollArea>
      </Paper>

      <Stack style={{ flex: 1, minWidth: 0 }} gap="xs">
        <Group justify="space-between">
          <Group gap="xs">
            <Title order={3}>{table?.name ?? t("nav.explore")}</Title>
            {table?.kind && (
              <Tooltip label={t(`explore.kindHelp.${table.group === "history" ? "history" : table.kind}`, "")}
                multiline w={380} withArrow>
                <Badge variant="light" style={{ cursor: "help" }}>
                  {table.group === "history" ? t("explore.groups.history") : t(`explore.kinds.${table.kind}`, table.kind)}
                </Badge>
              </Tooltip>
            )}
            {total !== null && (
              <Text size="sm" c="dimmed">
                {t("explore.rows", { count: total })}
              </Text>
            )}
          </Group>
          <Group gap="xs">
            <Popover position="bottom-end" withinPortal shadow="md">
              <Popover.Target>
                <Tooltip label={t("explore.columns")}>
                  <ActionIcon variant="default" size="lg">
                    <IconColumns size={18} />
                  </ActionIcon>
                </Tooltip>
              </Popover.Target>
              <Popover.Dropdown>
                <ScrollArea.Autosize mah={420} w={300}>
                  <Stack gap={4}>
                    {table?.columns.map((c) => (
                      <Checkbox
                        key={c.name}
                        size="xs"
                        label={c.masked ? `🔒 ${c.name}` : c.name}
                        checked={!hiddenCols.has(c.name)}
                        onChange={() => toggleColumn(c.name)}
                      />
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              </Popover.Dropdown>
            </Popover>
            <Button variant="default" leftSection={<IconSitemap size={16} />} onClick={openInQuery}>
              {t("explore.openInQuery")}
            </Button>
            <ExportMenu
              source={lastRequest ? { browse: lastRequest } : null}
              baseName={table?.name ?? "export"}
              onResult={(msg, ok) => setNotice({ msg, ok })}
            />
          </Group>
        </Group>
        {notice && (
          <Alert color={notice.ok ? "teal" : "red"} withCloseButton onClose={() => setNotice(null)} py={6}>
            {notice.msg}
          </Alert>
        )}
        {error && (
          <Alert color="red" withCloseButton onClose={() => setError(null)} py={6}>
            {error}
          </Alert>
        )}
        <div style={{ flex: 1, minHeight: 300 }}>
          {table && datasource ? (
            <AgGridReact
              key={`${table.name}:${visibleColumns.length}`}
              theme={theme}
              localeText={gridLocale(i18n.language)}
              columnDefs={defs}
              defaultColDef={{ resizable: true }}
              rowModelType="infinite"
              datasource={datasource}
              cacheBlockSize={200}
              maxBlocksInCache={20}
              tooltipShowDelay={300}
              enableCellTextSelection
              onGridReady={(e) => (apiRef.current = e.api)}
            />
          ) : (
            <Loader />
          )}
        </div>
      </Stack>
    </Group>
  );
}
