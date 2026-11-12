import {
  Alert,
  Autocomplete,
  Badge,
  Button,
  Group,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
} from "@mantine/core";
import { IconKey, IconPlugConnected, IconTrash } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { aiApi, type AiProvider, type AiStatus, type Settings } from "../api";

interface Props {
  ai: Settings["ai"];
  onChange: (ai: Settings["ai"]) => void;
}

const PROVIDERS: { value: AiProvider; label: string }[] = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
];

/** Provider, model, API key (kept in the Windows Credential Manager) and connection test. */
export default function AiSettings({ ai, onChange }: Props) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [key, setKey] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const refresh = () => aiApi.status().then(setStatus).catch(() => setStatus(null));
  useEffect(() => {
    void refresh();
  }, []);

  const provider = ai.provider;
  const hasKey = provider !== "none" && status?.keys[provider];
  const defaultModel = provider !== "none" ? status?.default_models[provider] : "";

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ ok: false, text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const saveKey = () =>
    run(async () => {
      await aiApi.saveKey(provider, key);
      setKey("");
      await refresh();
      setMsg({ ok: true, text: t("ai.keySaved") });
    });
  const removeKey = () =>
    run(async () => {
      await aiApi.deleteKey(provider);
      await refresh();
      setMsg({ ok: true, text: t("ai.keyDeleted") });
    });
  const test = () =>
    run(async () => {
      const r = await aiApi.test(provider);
      setModels(r.models);
      setMsg({ ok: true, text: t("ai.testOk", { count: r.models.length }) });
    });

  return (
    <Stack gap="sm">
      <Group grow align="flex-start">
        <Select
          label={t("settings.aiProvider")}
          value={provider}
          allowDeselect={false}
          onChange={(v) => {
            setModels([]);
            setMsg(null);
            onChange({ ...ai, provider: (v ?? "none") as AiProvider, model: "" });
          }}
          data={[{ value: "none", label: t("settings.aiNone") }, ...PROVIDERS]}
        />
        <Autocomplete
          label={t("settings.aiModel")}
          placeholder={defaultModel || t("ai.modelPlaceholder")}
          description={defaultModel ? t("ai.modelDefault", { model: defaultModel }) : t("ai.modelRequired")}
          value={ai.model}
          disabled={provider === "none"}
          data={models}
          limit={50}
          onChange={(v) => onChange({ ...ai, model: v })}
        />
      </Group>

      {provider !== "none" && (
        <Stack gap={6}>
          <Group gap="xs" align="flex-end">
            <PasswordInput
              style={{ flex: 1 }}
              label={t("ai.apiKey")}
              placeholder={hasKey ? t("ai.keyStoredPlaceholder") : t("ai.keyPlaceholder")}
              value={key}
              onChange={(e) => setKey(e.currentTarget.value)}
              leftSection={<IconKey size={14} />}
              autoComplete="off"
            />
            <Button onClick={saveKey} loading={busy} disabled={!key.trim()}>
              {t("ai.saveKey")}
            </Button>
          </Group>
          <Group gap="xs">
            {hasKey ? (
              <Badge color="teal" variant="light">{t("ai.keyStored")}</Badge>
            ) : (
              <Badge color="gray" variant="light">{t("ai.keyMissing")}</Badge>
            )}
            <Button size="xs" variant="default" leftSection={<IconPlugConnected size={14} />}
              onClick={test} disabled={!hasKey} loading={busy}>
              {t("ai.test")}
            </Button>
            <Button size="xs" variant="subtle" color="red" leftSection={<IconTrash size={14} />}
              onClick={removeKey} disabled={!hasKey}>
              {t("ai.deleteKey")}
            </Button>
          </Group>
          <Text size="xs" c="dimmed">{t("ai.keyHint")}</Text>
        </Stack>
      )}
      {msg && (
        <Alert color={msg.ok ? "teal" : "red"} py={6} withCloseButton onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}
      <Switch
        checked={ai.confirm_before_send}
        onChange={(e) => onChange({ ...ai, confirm_before_send: e.currentTarget.checked })}
        label={t("settings.aiConfirm")}
        description={t("ai.confirmHint")}
      />
    </Stack>
  );
}
