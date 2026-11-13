import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Collapse,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { IconChevronRight, IconLock, IconStar, IconStarFilled } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  playersApi,
  type PlayerAttribute,
  type PlayerCard,
  type PlayerKey,
  type PlayerStats,
} from "../api";
import {
  SECTION_COLORS,
  formatPositionLong,
  longDate,
  money,
  monthYear,
  num,
  ordinal,
  prettify,
} from "../lib/playerFormat";
import AttributeWheel from "./AttributeWheel";

interface Props {
  playerKey: PlayerKey | null;
  starred: boolean;
  onToggleStar: () => void;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600} lts={1}>{label}</Text>
      <Text fw={500}>{value}</Text>
    </Stack>
  );
}

function AttributeColumn({ title, section, items }: {
  title: string;
  section: string;
  items: PlayerAttribute[];
}) {
  const { t } = useTranslation();
  return (
    <Stack gap={4}>
      <Text size="xs" fw={700} tt="uppercase" lts={1} c={SECTION_COLORS[section]}>{title}</Text>
      {items.map((a) => (
        <Group key={a.key} gap={6} justify="space-between" wrap="nowrap">
          <Box style={{ flex: 1, minWidth: 0 }}>
            <Text size="sm" truncate>{t(`players.attr.${a.key}`)}</Text>
            <Box h={3} bg="var(--mantine-color-gray-2)">
              <Box h={3} w={`${a.rank ?? 0}%`} bg={SECTION_COLORS[section]} />
            </Box>
          </Box>
          <Text size="sm" fw={600} w={22} ta="right">
            {a.hidden ? <IconLock size={12} /> : (a.value ?? "–")}
          </Text>
        </Group>
      ))}
    </Stack>
  );
}

function AttributesTab({ card }: { card: PlayerCard }) {
  const { t } = useTranslation();
  const [more, setMore] = useState(false);
  const gk = card.group === "goalkeepers";
  const first = gk ? "goalkeeping" : "technical";
  const extra = gk ? ["technical", "hidden"] : ["goalkeeping", "hidden"];
  return (
    <Stack gap="sm">
      <SimpleGrid cols={3} spacing="md">
        {[first, "mental", "physical"].map((s) => (
          <AttributeColumn key={s} section={s} title={t(`players.sections.${s}`)}
            items={card.attributes[s] ?? []} />
        ))}
      </SimpleGrid>
      <UnstyledButton onClick={() => setMore((m) => !m)}>
        <Group gap={4}>
          <IconChevronRight size={14} style={{ transform: more ? "rotate(90deg)" : undefined }} />
          <Text size="sm" fw={600}>{t(gk ? "players.moreAttributesGk" : "players.moreAttributes")}</Text>
        </Group>
      </UnstyledButton>
      <Collapse expanded={more}>
        <SimpleGrid cols={2} spacing="md">
          {extra.map((s) => (
            <AttributeColumn key={s} section={s} title={t(`players.sections.${s}`)}
              items={card.attributes[s] ?? []} />
          ))}
        </SimpleGrid>
      </Collapse>
      <Text size="sm" c="dimmed">
        {card.group
          ? t("players.barsHint", { group: t(`players.groups.${card.group}`) })
          : t("players.noGroup")}
      </Text>
    </Stack>
  );
}

// pitch layout: [position key, x %, y %]
const PITCH: [string, number, number][] = [
  ["stc", 50, 8], ["aml", 15, 23], ["amc", 50, 23], ["amr", 85, 23],
  ["ml", 15, 38], ["mc", 50, 38], ["mr", 85, 38],
  ["wbl", 15, 53], ["dm", 50, 53], ["wbr", 85, 53],
  ["dl", 15, 68], ["dc", 50, 68], ["dr", 85, 68], ["sw", 50, 81], ["gk", 50, 94],
];

function PositionsTab({ card }: { card: PlayerCard }) {
  const { t } = useTranslation();
  const style = (v: number | null) => {
    if (v !== null && v >= 19) return { bg: "#13775a", fg: "white", border: "#13775a" };
    if (v !== null && v >= 15) return { bg: "#cfe8de", fg: "#13573f", border: "#9cc9b6" };
    return { bg: "white", fg: "#555", border: "#bbb" };
  };
  return (
    <Stack gap="sm">
      <Box pos="relative" mx="auto" w={280} h={420}
        style={{ background: "#eef3ec", border: "2px solid #c9d6c6", borderRadius: 8 }}>
        <Box pos="absolute" left="25%" right="25%" top={0} h={60}
          style={{ border: "2px solid #c9d6c6", borderTop: 0 }} />
        <Box pos="absolute" left="25%" right="25%" bottom={0} h={60}
          style={{ border: "2px solid #c9d6c6", borderBottom: 0 }} />
        <Box pos="absolute" left={0} right={0} top="50%" style={{ borderTop: "2px solid #c9d6c6" }} />
        {PITCH.map(([key, x, y]) => {
          const v = card.positions[key];
          const s = style(v);
          return (
            <Stack key={key} gap={0} align="center" pos="absolute"
              style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)" }}>
              <Box w={32} h={32} style={{ borderRadius: "50%", background: s.bg, color: s.fg,
                border: `2px solid ${s.border}`, display: "flex", alignItems: "center",
                justifyContent: "center", fontWeight: 700, fontSize: 13 }}>
                {v ?? "–"}
              </Box>
              <Text size="9px" c="dimmed" fw={600}>{key.toUpperCase()}</Text>
            </Stack>
          );
        })}
      </Box>
      <Table>
        <Table.Tbody>
          <Table.Tr>
            <Table.Td c="dimmed">{t("players.natural")}</Table.Td>
            <Table.Td ta="right">{formatPositionLong(card.natural_positions) || "–"}</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Td c="dimmed">{t("players.alsoPlays")}</Table.Td>
            <Table.Td ta="right">{formatPositionLong(card.accomplished_positions) || "–"}</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Td c="dimmed">{t("players.rankedAs")}</Table.Td>
            <Table.Td ta="right">{card.group ? t(`players.groups.${card.group}`) : "–"}</Table.Td>
          </Table.Tr>
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

function StatsTab({ card, playerKey }: { card: PlayerCard; playerKey: PlayerKey }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [kind, setKind] = useState(card.stats?.kind ?? "");
  const [stats, setStats] = useState<PlayerStats | null>(card.stats);
  const [loading, setLoading] = useState(false);

  const change = async (k: string | null) => {
    if (!k) return;
    setKind(k);
    setLoading(true);
    try {
      setStats(await playersApi.stats(playerKey, k));
    } finally {
      setLoading(false);
    }
  };

  if (!card.stat_kinds.length) return <Text c="dimmed">{t("players.noStats")}</Text>;
  const value = (v: number | null, kindOf: string, key: string) => {
    if (v === null) return "–";
    if (kindOf === "rate") return key === "expected_goals_per_shot" ? num(v, lang, 2) : `${Math.round(v * 100)}%`;
    if (kindOf === "rating") return num(v, lang, 2);
    return Number.isInteger(v) ? num(v, lang) : num(v, lang, key === "distance_km" ? 1 : 2);
  };
  const sections = [...new Set((stats?.rows ?? []).map((r) => r.section))];
  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Select value={kind} allowDeselect={false} w={240} onChange={change}
          data={card.stat_kinds.map((k) => ({ value: k, label: t(`players.kinds.${k}`) }))} />
        {loading && <Loader size="xs" />}
      </Group>
      {!stats?.rows.length ? (
        <Text c="dimmed" size="sm">{t("players.noStats")}</Text>
      ) : (
        <Table verticalSpacing={2} fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th />
              <Table.Th ta="right">{t("players.total")}</Table.Th>
              <Table.Th ta="right">{t("players.per90")}</Table.Th>
              <Table.Th ta="right">{t("players.rank")}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sections.map((section) => [
              <Table.Tr key={section}>
                <Table.Td colSpan={4} pt="sm">
                  <Text size="xs" fw={700} tt="uppercase" lts={1} c="dimmed">
                    {t(`players.statSections.${section}`)}
                  </Text>
                </Table.Td>
              </Table.Tr>,
              ...stats.rows.filter((r) => r.section === section).map((r) => (
                <Table.Tr key={r.key}>
                  <Table.Td>{t(`players.stat.${r.key}`)}</Table.Td>
                  <Table.Td ta="right">{value(r.total, r.kind, r.key)}</Table.Td>
                  <Table.Td ta="right">{r.per90 === null ? "" : num(r.per90, lang, 2)}</Table.Td>
                  <Table.Td>
                    {r.rank !== null && (
                      <Group gap={6} justify="flex-end" wrap="nowrap">
                        <Box w={40} h={3} bg="var(--mantine-color-gray-2)">
                          <Box h={3} w={`${r.rank}%`} bg="var(--mantine-color-dark-6)" />
                        </Box>
                        <Text size="xs" w={20} ta="right">{r.rank}</Text>
                      </Group>
                    )}
                  </Table.Td>
                </Table.Tr>
              )),
            ])}
          </Table.Tbody>
        </Table>
      )}
      <Text size="xs" c="dimmed">
        {t("players.statsHint", { n: stats?.group_size ?? 0 })}
      </Text>
    </Stack>
  );
}

function PersonalityTab({ card }: { card: PlayerCard }) {
  const { t, i18n } = useTranslation();
  return (
    <Stack gap="sm">
      <Text size="xs" fw={700} tt="uppercase" lts={1} c={SECTION_COLORS.hidden}>
        {t("players.sections.personality")}
      </Text>
      {card.personality.map((p) => (
        <Group key={p.key} gap={6} justify="space-between" wrap="nowrap">
          <Box style={{ flex: 1 }}>
            <Text size="sm">
              {t(`players.personality.${p.key}`)}
              {p.key === "controversy" && <Text span c="dimmed" size="xs"> ({t("players.lowIsGood")})</Text>}
            </Text>
            <Box h={3} bg="var(--mantine-color-gray-2)">
              <Box h={3} w={`${((p.value ?? 0) / 20) * 100}%`} bg={SECTION_COLORS.hidden} />
            </Box>
          </Box>
          <Text size="sm" fw={600} w={22} ta="right">
            {p.hidden ? <IconLock size={12} /> : (p.value ?? "–")}
          </Text>
        </Group>
      ))}
      <Text size="xs" fw={700} tt="uppercase" lts={1} c="dimmed" mt="sm">{t("players.traits")}</Text>
      <Group gap={6}>
        {card.traits.length ? card.traits.map((tr) => (
          <Badge key={tr} variant="light" color="gray" tt="none" size="lg">{prettify(tr)}</Badge>
        )) : <Text size="sm" c="dimmed">–</Text>}
      </Group>
      <Text size="xs" fw={700} tt="uppercase" lts={1} c="dimmed" mt="sm">{t("players.reputation")}</Text>
      {(["current", "home", "world"] as const).map((k) => (
        <Group key={k} justify="space-between">
          <Text size="sm">{t(`players.rep.${k}`)}</Text>
          <Text size="sm">{num(card.reputation[k], i18n.language)}</Text>
        </Group>
      ))}
    </Stack>
  );
}

function ContractTab({ card }: { card: PlayerCard }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const c = card.contract;
  const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v / 100)}%`);
  const rows: [string, string][] = [
    [t("players.contract.club"), c?.club_name ?? card.club_name ?? "–"],
    [t("players.contract.squadStatus"), c?.squad_status ? prettify(c.squad_status) : "–"],
    [t("players.contract.type"), c?.kind ? prettify(c.kind) : "–"],
    [t("players.contract.wage"), `${money(c?.wage ?? card.wage, lang)} ${t("players.perWeek")}`],
    [t("players.contract.started"), longDate(c?.start, lang)],
    [t("players.contract.expires"), longDate(c?.end ?? card.contract_end, lang)],
    [t("players.value"), money(card.transfer_value, lang)],
    [t("players.contract.joined"), longDate(card.club_join_date, lang)],
    [t("players.contract.born"), longDate(card.birth_date, lang)],
    [t("players.contract.height"), card.height_cm ? `${card.height_cm} cm` : "–"],
    [t("players.contract.condition"), pct(card.condition)],
    [t("players.contract.sharpness"), pct(card.match_sharpness)],
  ];
  if (card.on_loan) {
    rows.splice(1, 0, [t("players.contract.loanFrom"), card.loan_parent_club_name ?? "–"]);
    rows.splice(2, 0, [t("players.contract.loanEnd"), longDate(c?.loan_end, lang)]);
  }
  const clauses = (c?.clauses ?? []).filter((x) => x.kind !== "unknown");
  return (
    <Stack gap="xs">
      <Table verticalSpacing={4}>
        <Table.Tbody>
          {rows.map(([k, v]) => (
            <Table.Tr key={k}>
              <Table.Td c="dimmed">{k}</Table.Td>
              <Table.Td ta="right">{v}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {clauses.length > 0 && (
        <>
          <Text size="xs" fw={700} tt="uppercase" lts={1} c="dimmed">{t("players.clauses")}</Text>
          <Table verticalSpacing={4}>
            <Table.Tbody>
              {clauses.map((x, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{prettify(x.kind)}</Table.Td>
                  <Table.Td ta="right">
                    {x.value !== null ? money(x.value, lang) : num(x.parameter, lang)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
      <Text size="xs" c="dimmed">{t("players.moneyHint")}</Text>
    </Stack>
  );
}

export default function PlayerCardPanel({ playerKey, starred, onToggleStar }: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [card, setCard] = useState<PlayerCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<string | null>("attributes");

  useEffect(() => {
    setError(null);
    if (!playerKey) {
      setCard(null);
      return;
    }
    let alive = true;
    playersApi
      .card(playerKey)
      .then((c) => alive && setCard(c))
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [playerKey]);

  if (!playerKey) return <Text c="dimmed">{t("players.pick")}</Text>;
  if (error) return <Alert color="red">{error}</Alert>;
  if (!card || card.uid !== playerKey.uid) return <Loader />;

  const sections: [string, PlayerAttribute[]][] = (
    card.group === "goalkeepers" ? ["goalkeeping", "mental", "physical"] : ["technical", "mental", "physical"]
  ).map((s) => [s, card.attributes[s] ?? []]);
  const season = card.season.apps
    ? t("players.seasonLine", { apps: card.season.apps, goals: card.season.goals ?? 0 })
    : "–";
  const centre = card.wheel.percentile === null ? "" : ordinal(card.wheel.percentile, lang);

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={0}>
          <Text fz={28} fw={800} lh={1.1}>{card.name}</Text>
          <Text c="dimmed">
            {[card.age, formatPositionLong(card.natural_positions), card.club_name]
              .filter((x) => x !== null && x !== "").join(", ")}
          </Text>
        </Stack>
        <ActionIcon variant="subtle" color="yellow" size="lg" onClick={onToggleStar}
          aria-label={t("players.shortlist")}>
          {starred ? <IconStarFilled size={20} /> : <IconStar size={20} />}
        </ActionIcon>
      </Group>
      <Group justify="space-between" wrap="nowrap">
        <Group gap="lg" wrap="nowrap">
          <Stack gap={0}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600} lts={1}>{t("players.current")}</Text>
            <Text fz={44} fw={800} lh={1}>{card.ca_hidden ? "?" : (card.ability_current ?? "–")}</Text>
          </Stack>
          <Stack gap={0}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600} lts={1}>{t("players.potential")}</Text>
            <Text fz={44} fw={800} lh={1} c="red.7">
              {card.pa_hidden ? "?" : (card.ability_potential ?? "–")}
            </Text>
          </Stack>
        </Group>
        <AttributeWheel sections={sections} percentile={card.wheel.percentile}
          label={card.wheel.label} centre={centre} size={140} />
      </Group>
      <SimpleGrid cols={3} spacing="xs" style={{ borderTop: "1px solid var(--mantine-color-gray-3)" }} pt="xs">
        <Fact label={t("players.value")} value={money(card.transfer_value, lang)} />
        <Fact label={t("players.wage")} value={`${money(card.wage, lang)}${t("players.perWeekShort")}`} />
        <Fact label={t("players.expires")} value={monthYear(card.contract_end, lang)} />
        <Fact label={t("players.feet")}
          value={`${t("players.leftShort")} ${card.left_foot ?? "–"}, ${t("players.rightShort")} ${card.right_foot ?? "–"}`} />
        <Fact label={t("players.season")} value={season} />
        <Fact label={t("players.rating")} value={card.season.rating ? num(card.season.rating, lang, 2) : "–"} />
      </SimpleGrid>
      <Tabs value={tab} onChange={setTab} styles={{ tab: { paddingInline: 8 } }}>
        <Tabs.List>
          <Tabs.Tab value="attributes">{t("players.tabs.attributes")}</Tabs.Tab>
          <Tabs.Tab value="positions">{t("players.tabs.positions")}</Tabs.Tab>
          <Tabs.Tab value="stats">{t("players.tabs.stats")}</Tabs.Tab>
          <Tabs.Tab value="personality">{t("players.tabs.personality")}</Tabs.Tab>
          <Tabs.Tab value="contract">{t("players.tabs.contract")}</Tabs.Tab>
        </Tabs.List>
        <Box pt="sm">
          {tab === "attributes" && <AttributesTab card={card} />}
          {tab === "positions" && <PositionsTab card={card} />}
          {tab === "stats" && <StatsTab key={card.uid} card={card} playerKey={playerKey} />}
          {tab === "personality" && <PersonalityTab card={card} />}
          {tab === "contract" && <ContractTab card={card} />}
        </Box>
      </Tabs>
      <Text size="xs" c="dimmed">{t("players.keysHint")}</Text>
    </Stack>
  );
}
