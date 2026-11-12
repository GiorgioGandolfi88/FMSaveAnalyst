import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Loader,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconArrowLeft, IconLock, IconSend } from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { aiApi, localized, type AiStatus, type Chat, type ChatEvent } from "../api";

interface Props {
  onOpenSettings: () => void;
}

type ToolEvent = Extract<ChatEvent, { type: "tool" }>;

function ToolCard({ e }: { e: ToolEvent }) {
  const { t } = useTranslation();
  const p = e.preview;
  const sql = typeof e.args.sql === "string" ? e.args.sql : null;
  const purpose = typeof e.args.purpose === "string" ? e.args.purpose : null;
  const color = { pending: "yellow", sent: "teal", declined: "gray" }[e.status];
  return (
    <Paper withBorder p="xs" bg="var(--mantine-color-default-hover)">
      <Group justify="space-between" mb={4}>
        <Text size="sm" fw={600}>
          {t(`ai.tools.${e.name}`, { defaultValue: e.name })}
          {e.name === "describe_table" && typeof e.args.table === "string" ? `: ${e.args.table}` : ""}
        </Text>
        <Group gap={4}>
          <Badge size="xs" variant="outline" color="gray">
            ≈ {Math.ceil(e.chars / 4).toLocaleString()} token
          </Badge>
          <Badge size="xs" color={color} variant="light">{t(`ai.status.${e.status}`)}</Badge>
        </Group>
      </Group>
      {purpose && <Text size="xs" c="dimmed" mb={4}>{purpose}</Text>}
      {sql && <Code block mb={4} style={{ fontSize: 11 }}>{sql}</Code>}
      {p.kind === "rows" && p.columns && p.rows && (
        <ScrollArea.Autosize mah={180}>
          <Table fz="xs" withTableBorder striped verticalSpacing={2}>
            <Table.Thead>
              <Table.Tr>{p.columns.map((c) => <Table.Th key={c}>{c}</Table.Th>)}</Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {p.rows.map((r, i) => (
                <Table.Tr key={i}>
                  {r.map((v, j) => <Table.Td key={j}>{v === null ? "∅" : String(v)}</Table.Td>)}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea.Autosize>
      )}
      {p.kind === "rows" && (
        <Text size="xs" c="dimmed">
          {t("ai.rowsSummary", { count: p.row_count ?? 0 })}
          {p.truncated ? ` · ${t("ai.truncated")}` : ""}
          {(p.row_count ?? 0) > (p.rows?.length ?? 0) ? ` · ${t("ai.previewOnly")}` : ""}
        </Text>
      )}
      {p.kind === "error" && <Text size="xs" c="red">{p.message ?? t("ai.toolError")}</Text>}
      {(p.kind === "tables" || p.kind === "columns") && (
        <Text size="xs" c="dimmed">{t("ai.schemaSummary", { count: p.count ?? 0 })}</Text>
      )}
    </Paper>
  );
}

function Message({ e }: { e: ChatEvent }) {
  if (e.type === "tool") return <ToolCard e={e} />;
  if (e.type === "error") return <Alert color="red" py={6}>{e.text}</Alert>;
  const mine = e.type === "user";
  return (
    <Group justify={mine ? "flex-end" : "flex-start"}>
      <Paper
        p="sm"
        maw="85%"
        radius="md"
        withBorder={!mine}
        bg={mine ? "var(--mantine-primary-color-light)" : undefined}
        className="ai-markdown"
      >
        {mine ? (
          <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{e.text}</Text>
        ) : (
          <Markdown remarkPlugins={[remarkGfm]}>{e.text}</Markdown>
        )}
      </Paper>
    </Group>
  );
}

export default function AiPage({ onOpenSettings }: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [chat, setChat] = useState<Chat | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    aiApi.status().then(setStatus).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat?.events.length, busy]);

  const act = async (fn: () => Promise<Chat>) => {
    setBusy(true);
    setError(null);
    try {
      setChat(await fn());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status) return error ? <Alert color="red">{error}</Alert> : <Loader />;

  const configured = status.provider !== "none" && status.keys[status.provider];
  if (!configured) {
    return (
      <Stack maw={720}>
        <Title order={2}>{t("nav.ai")}</Title>
        <Alert color="blue" title={t("ai.setupTitle")}>
          <Stack gap="xs">
            <Text size="sm">{t("ai.setupBody")}</Text>
            <Button w="fit-content" onClick={onOpenSettings}>{t("ai.openSettings")}</Button>
          </Stack>
        </Alert>
      </Stack>
    );
  }

  if (!chat) {
    return (
      <Stack>
        <Group justify="space-between">
          <Title order={2}>{t("nav.ai")}</Title>
          <Badge variant="light" size="lg" tt="none">
            {status.provider} · {status.model || "—"}
          </Badge>
        </Group>
        <Text size="sm" c="dimmed">{t("ai.intro")}</Text>
        {error && <Alert color="red">{error}</Alert>}
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {status.agents.map((a) => (
            <Card key={a.id} withBorder padding="md" style={{ cursor: busy ? "wait" : "pointer" }}
              onClick={() => !busy && act(() => aiApi.newChat(a.id))}>
              <Text fw={600}>{localized(a.name, lang)}</Text>
              <Text size="sm" c="dimmed">{localized(a.description, lang)}</Text>
            </Card>
          ))}
        </SimpleGrid>
        <Group gap={6}>
          <IconLock size={14} />
          <Text size="xs" c="dimmed">
            {status.confirm_before_send ? t("ai.privacyConfirm") : t("ai.privacyAuto")}
          </Text>
        </Group>
      </Stack>
    );
  }

  const agent = status.agents.find((a) => a.id === chat.agent);
  const pending = chat.status === "needs_approval";
  const send = () => {
    const msg = text.trim();
    if (!msg || busy || pending) return;
    setText("");
    setChat({ ...chat, events: [...chat.events, { type: "user", text: msg }] });
    void act(() => aiApi.send(chat.id, msg));
  };

  return (
    <Stack gap="sm" h="calc(100vh - 56px - 2 * var(--mantine-spacing-lg))">
      <Group justify="space-between">
        <Group gap="xs">
          <Button variant="default" size="xs" leftSection={<IconArrowLeft size={14} />}
            onClick={() => { void aiApi.close(chat.id); setChat(null); }}>
            {t("ai.newChat")}
          </Button>
          <Title order={3}>{agent ? localized(agent.name, lang) : chat.agent}</Title>
        </Group>
        <Text size="xs" c="dimmed">
          {chat.provider} · {chat.model} · {t("ai.usage", {
            input: chat.usage.input_tokens.toLocaleString(),
            output: chat.usage.output_tokens.toLocaleString(),
            sent: Math.ceil(chat.usage.sent_chars / 4).toLocaleString(),
          })}
        </Text>
      </Group>

      <ScrollArea style={{ flex: 1 }} offsetScrollbars>
        <Stack gap="sm" pr="xs">
          {chat.events.length === 0 && (
            <Text size="sm" c="dimmed">{t("ai.emptyChat")}</Text>
          )}
          {chat.events.map((e, i) => <Message key={i} e={e} />)}
          {busy && (
            <Group gap="xs"><Loader size="xs" /><Text size="sm" c="dimmed">{t("ai.thinking")}</Text></Group>
          )}
          <div ref={bottom} />
        </Stack>
      </ScrollArea>

      {error && <Alert color="red" withCloseButton onClose={() => setError(null)} py={6}>{error}</Alert>}
      {pending && (
        <Alert color="yellow" title={t("ai.approveTitle")} py="xs">
          <Group justify="space-between">
            <Text size="sm">{t("ai.approveBody")}</Text>
            <Group gap="xs">
              <Button size="xs" variant="default" disabled={busy}
                onClick={() => act(() => aiApi.approve(chat.id, false))}>
                {t("ai.decline")}
              </Button>
              <Button size="xs" loading={busy} onClick={() => act(() => aiApi.approve(chat.id, true))}>
                {t("ai.approve")}
              </Button>
            </Group>
          </Group>
        </Alert>
      )}
      <Group align="flex-end" gap="xs">
        <Textarea style={{ flex: 1 }} autosize minRows={1} maxRows={6}
          placeholder={t("ai.placeholder")} value={text} disabled={pending}
          onChange={(e) => setText(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }} />
        <Button leftSection={<IconSend size={16} />} onClick={send} loading={busy && !pending}
          disabled={!text.trim() || pending}>
          {t("ai.send")}
        </Button>
      </Group>
    </Stack>
  );
}
