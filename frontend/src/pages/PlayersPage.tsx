import {
  ActionIcon,
  Alert,
  Box,
  Chip,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Select,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import {
  IconSearch,
  IconSortAscending,
  IconSortDescending,
  IconStar,
  IconStarFilled,
} from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { playersApi, type PlayerKey, type PlayerList, type PlayerRow } from "../api";
import PlayerCardPanel from "../components/PlayerCardPanel";
import { formatPositions, longDate, money, num } from "../lib/playerFormat";

const PAGE = 100;

type Col = {
  key: string;
  align?: "left" | "right";
  width: number;
  render: (r: PlayerRow, lang: string) => string;
};

const COLUMNS: Col[] = [
  { key: "name", width: 165, render: (r) => r.name },
  { key: "age", align: "right", width: 44, render: (r) => String(r.age ?? "–") },
  { key: "pos", width: 80, render: (r) => formatPositions(r.natural_positions) },
  { key: "ca", align: "right", width: 44, render: (r) => String(r.ca ?? "–") },
  { key: "pa", align: "right", width: 44, render: (r) => String(r.pa ?? "–") },
  { key: "club", width: 150, render: (r) => r.club_name ?? "–" },
  { key: "value", align: "right", width: 58, render: (r, l) => money(r.transfer_value, l) },
  { key: "wage", align: "right", width: 58, render: (r, l) => money(r.contract_wage, l) },
  { key: "expires", align: "right", width: 92, render: (r, l) => longDate(r.contract_end, l) },
  { key: "apps", align: "right", width: 50, render: (r) => (r.apps === null ? "–" : String(r.apps)) },
  { key: "goals", align: "right", width: 50, render: (r) => (r.goals === null ? "–" : String(r.goals)) },
  { key: "assists", align: "right", width: 50, render: (r) => (r.assists === null ? "–" : String(r.assists)) },
  { key: "rating", align: "right", width: 56, render: (r, l) => num(r.rating, l, 2) },
];
const SHADED: Record<string, keyof PlayerRow> = {
  apps: "apps",
  goals: "goals",
  assists: "assists",
  rating: "rating",
};

const keyOf = (k: PlayerKey) => `${k.uid}|${k.birth_date}`;

export default function PlayersPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [meta, setMeta] = useState<{ groups: string[]; kinds: string[] } | null>(null);
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 300);
  const [group, setGroup] = useState<string | null>(null);
  const [kind, setKind] = useState("league");
  const [onlyShortlist, setOnlyShortlist] = useState(false);
  const [sort, setSort] = useState<{ key: string; desc: boolean }>({ key: "pa", desc: true });
  const [list, setList] = useState<PlayerList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PlayerKey | null>(null);
  const [shortlist, setShortlist] = useState<PlayerKey[]>([]);
  const request = useRef(0);
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
    playersApi
      .meta()
      .then((m) => setMeta({ groups: Object.keys(m.groups), kinds: m.stat_kinds }))
      .catch((e) => setError(String(e)));
    playersApi.shortlist().then(setShortlist).catch(() => setShortlist([]));
  }, []);

  const fetchPage = useCallback(
    async (offset: number) => {
      const id = ++request.current;
      setLoading(true);
      try {
        const page = await playersApi.list({
          search: debounced, group: group ?? "", shortlist_only: onlyShortlist, kind,
          sort: sort.key, desc: sort.desc, offset, limit: PAGE,
        });  // prettier-ignore
        if (id !== request.current) return;
        if (offset === 0 && sort.key === "pa" && page.masked.includes("pa")) {
          setSort({ key: "ca", desc: true }); // potential is hidden: sort by current ability
          return;
        }
        setList((prev) =>
          offset === 0 || !prev ? page : { ...page, rows: [...prev.rows, ...page.rows] });
        if (offset === 0) {
          viewport.current?.scrollTo({ top: 0 });
          setSelected((s) => s ?? (page.rows[0] ? { uid: page.rows[0].uid, birth_date: page.rows[0].birth_date } : null));
        }
      } catch (e) {
        if (id === request.current) setError(String(e));
      } finally {
        if (id === request.current) setLoading(false);
      }
    },
    [debounced, group, onlyShortlist, kind, sort],
  );

  useEffect(() => {
    void fetchPage(0);
  }, [fetchPage]);

  const starred = useMemo(() => new Set(shortlist.map(keyOf)), [shortlist]);
  const toggleStar = useCallback(
    (k: PlayerKey) => {
      const next = starred.has(keyOf(k))
        ? shortlist.filter((x) => keyOf(x) !== keyOf(k))
        : [...shortlist, { uid: k.uid, birth_date: k.birth_date }];
      setShortlist(next);
      playersApi.saveShortlist(next).catch((e) => setError(String(e)));
    },
    [shortlist, starred],
  );

  const rows = list?.rows ?? [];
  const index = selected ? rows.findIndex((r) => keyOf(r) === keyOf(selected)) : -1;

  // j / k move through the list, s adds to the shortlist
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable) return;
      if (e.key === "j" || e.key === "k") {
        const next = rows[Math.max(0, Math.min(rows.length - 1, index + (e.key === "j" ? 1 : -1)))];
        if (next) {
          setSelected({ uid: next.uid, birth_date: next.birth_date });
          document.getElementById(`player-${keyOf(next)}`)?.scrollIntoView({ block: "nearest" });
        }
      } else if (e.key === "s" && selected) {
        toggleStar(selected);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, index, selected, toggleStar]);

  const onScroll = () => {
    const el = viewport.current;
    if (!el || loading || !list || rows.length >= list.total) return;
    if (el.scrollTop + el.clientHeight > el.scrollHeight - 400) void fetchPage(rows.length);
  };

  const sortBy = (key: string) => {
    if (key === "pos") return;
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key !== "name" && key !== "club" }));
  };

  const shade = (col: string, r: PlayerRow) => {
    const field = SHADED[col];
    const cut = list?.cutoffs[field as string];
    const v = field ? (r[field] as number | null) : null;
    if (!cut || v === null || v === undefined) return undefined;
    if (v >= cut[1]) return { bg: "var(--mantine-color-dark-5)", c: "white" };
    if (v >= cut[0]) return { bg: "var(--mantine-color-gray-2)", c: undefined };
    return undefined;
  };

  if (error) return <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>;

  const sortLabel = t(`players.cols.${sort.key}`);
  return (
    <Group align="flex-start" gap="md" wrap="nowrap" h="calc(100vh - 100px)">
      <Paper withBorder p="sm" style={{ flex: 1, minWidth: 0, height: "100%", display: "flex", flexDirection: "column" }}>
        <Group justify="space-between" mb="xs" wrap="nowrap">
          <Group gap="sm" align="baseline" wrap="nowrap">
            <Title order={2}>{t("players.title")}</Title>
            <Text c="dimmed" size="sm">
              {list ? t("players.count", { n: num(list.total, lang), sort: sortLabel }) : ""}
            </Text>
            {loading && <Loader size="xs" />}
          </Group>
        </Group>
        <Group gap="xs" mb="xs">
          <TextInput leftSection={<IconSearch size={14} />} placeholder={t("players.search")} w={220}
            value={search} onChange={(e) => setSearch(e.currentTarget.value)} />
          <Select placeholder={t("players.allRoles")} clearable w={200} value={group} onChange={setGroup}
            data={(meta?.groups ?? []).map((g) => ({ value: g, label: t(`players.groups.${g}`) }))} />
          <Select w={220} value={kind} allowDeselect={false} onChange={(v) => setKind(v ?? "league")}
            data={(meta?.kinds ?? ["league"]).map((k) => ({ value: k, label: t(`players.kinds.${k}`) }))} />
          <Chip checked={onlyShortlist} onChange={setOnlyShortlist} icon={<IconStarFilled size={12} />}>
            {t("players.shortlistOnly", { n: shortlist.length })}
          </Chip>
        </Group>
        <ScrollArea viewportRef={viewport} onScrollPositionChange={onScroll} style={{ flex: 1 }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
            <thead style={{ position: "sticky", top: 0, background: "var(--mantine-color-body)", zIndex: 1 }}>
              <tr style={{ borderBottom: "2px solid var(--mantine-color-dark-4)" }}>
                <th style={{ width: 28 }} />
                {COLUMNS.map((c) => (
                  <th key={c.key} onClick={() => sortBy(c.key)}
                    style={{ width: c.width, textAlign: c.align ?? "left", padding: "6px 4px",
                      cursor: c.key === "pos" ? "default" : "pointer", whiteSpace: "nowrap",
                      fontWeight: 600, background: sort.key === c.key ? "var(--mantine-color-gray-1)" : undefined }}>
                    {t(`players.cols.${c.key}`)}
                    {sort.key === c.key && (sort.desc
                      ? <IconSortDescending size={12} style={{ marginLeft: 2 }} />
                      : <IconSortAscending size={12} style={{ marginLeft: 2 }} />)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const k = keyOf(r);
                const active = selected !== null && k === keyOf(selected);
                return (
                  <tr key={k} id={`player-${k}`}
                    onClick={() => setSelected({ uid: r.uid, birth_date: r.birth_date })}
                    style={{ cursor: "pointer", borderBottom: "1px solid var(--mantine-color-gray-2)",
                      background: active ? "var(--mantine-color-yellow-0)" : undefined,
                      boxShadow: active ? "inset 3px 0 0 var(--mantine-color-dark-6)" : undefined }}>
                    <td style={{ padding: "4px 2px" }}>
                      <ActionIcon size="sm" variant="subtle" color="yellow"
                        onClick={(e) => { e.stopPropagation(); toggleStar(r); }}
                        aria-label={t("players.shortlist")}>
                        {starred.has(k) ? <IconStarFilled size={14} /> : <IconStar size={14} color="gray" />}
                      </ActionIcon>
                    </td>
                    {COLUMNS.map((c) => {
                      const s = shade(c.key, r);
                      const strong = c.key === "name" || c.key === "ca" || c.key === "pa";
                      return (
                        <td key={c.key} style={{ textAlign: c.align ?? "left", padding: "5px 4px",
                          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                          maxWidth: c.width, fontWeight: strong ? 600 : undefined,
                          color: c.key === "pos" ? "var(--mantine-color-dimmed)" : undefined }}>
                          {s ? (
                            <Box component="span" px={6} py={1} bg={s.bg} c={s.c}
                              style={{ borderRadius: 4, fontWeight: 600 }}>
                              {c.render(r, lang)}
                            </Box>
                          ) : c.render(r, lang)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {list && rows.length === 0 && <Text c="dimmed" p="md">{t("players.none")}</Text>}
        </ScrollArea>
      </Paper>
      <Paper withBorder p="md" w={460} h="100%" style={{ flexShrink: 0, overflowY: "auto" }}>
        <PlayerCardPanel playerKey={selected}
          starred={selected !== null && starred.has(keyOf(selected))}
          onToggleStar={() => selected && toggleStar(selected)} />
      </Paper>
    </Group>
  );
}
