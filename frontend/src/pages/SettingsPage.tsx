import {
  Alert,
  Button,
  Checkbox,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api, openExternal, updatesApi, type AppInfo, type Language, type Settings } from "../api";
import AiSettings from "../components/AiSettings";

interface Props {
  settings: Settings;
  info: AppInfo;
  onSaved: (s: Settings) => void;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper withBorder p="md">
      <Stack gap="sm">
        <Title order={4}>{title}</Title>
        {children}
      </Stack>
    </Paper>
  );
}

export default function SettingsPage({ settings, info, onSaved }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Settings>(settings);
  const [status, setStatus] = useState<{ ok: boolean; detail?: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const setMask = (key: keyof Settings["masking"], value: boolean) =>
    setDraft((d) => ({ ...d, masking: { ...d.masking, [key]: value } }));

  const [checking, setChecking] = useState(false);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updateUrl, setUpdateUrl] = useState<string | null>(null);
  const checkNow = async () => {
    setChecking(true);
    setUpdateUrl(null);
    try {
      const u = await updatesApi.check(true);
      if (u.error) setUpdateMsg(t("updates.offline"));
      else if (u.update_available) {
        setUpdateMsg(t("updates.available", { version: u.latest }));
        setUpdateUrl(u.url ?? null);
      } else if (!u.latest) setUpdateMsg(t("updates.noRelease"));
      else setUpdateMsg(t("updates.upToDate", { version: u.current }));
    } catch (e) {
      setUpdateMsg(String(e));
    } finally {
      setChecking(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const saved = await api.saveSettings(draft);
      setDraft(saved);
      onSaved(saved);
      setStatus({ ok: true });
    } catch (e) {
      setStatus({ ok: false, detail: String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack maw={860}>
      <Group justify="space-between">
        <Title order={2}>{t("settings.title")}</Title>
        <Button onClick={save} loading={saving}>
          {t("settings.save")}
        </Button>
      </Group>
      {status && (
        <Alert color={status.ok ? "teal" : "red"} withCloseButton onClose={() => setStatus(null)}>
          {status.ok ? t("settings.saved") : `${t("settings.saveError")}: ${status.detail}`}
        </Alert>
      )}

      <Section title={t("settings.general")}>
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            {t("settings.language")}
          </Text>
          <SegmentedControl
            w={220}
            value={draft.language}
            onChange={(v) => set("language", v as Language)}
            data={[
              { value: "it", label: "Italiano" },
              { value: "en", label: "English" },
            ]}
          />
        </Stack>
        <Group gap="xs">
          <Button size="xs" variant="default" loading={checking} onClick={checkNow}>
            {t("updates.check")}
          </Button>
          {updateMsg && <Text size="sm" c="dimmed">{updateMsg}</Text>}
          {updateUrl && (
            <Button size="xs" variant="light" onClick={() => openExternal(updateUrl)}>
              {t("updates.download")}
            </Button>
          )}
        </Group>
        <Switch
          checked={draft.check_updates}
          onChange={(e) => set("check_updates", e.currentTarget.checked)}
          label={t("settings.checkUpdates")}
          description={t("settings.checkUpdatesDesc")}
        />
      </Section>

      <Section title={t("settings.paths")}>
        <TextInput
          label={t("settings.fmSaveDir")}
          value={draft.fm_save_dir}
          onChange={(e) => set("fm_save_dir", e.currentTarget.value)}
        />
        <TextInput
          label={t("settings.careersDir")}
          value={draft.careers_dir}
          onChange={(e) => set("careers_dir", e.currentTarget.value)}
        />
        <TextInput
          label={t("settings.referenceDb")}
          value={draft.reference_db}
          onChange={(e) => set("reference_db", e.currentTarget.value)}
        />
      </Section>

      <Section title={t("settings.masking")}>
        <Text size="sm" c="dimmed">
          {t("settings.maskingDesc")}
        </Text>
        <Checkbox
          checked={draft.masking.potential_ability}
          onChange={(e) => setMask("potential_ability", e.currentTarget.checked)}
          label={t("settings.maskPotential")}
        />
        <Checkbox
          checked={draft.masking.current_ability}
          onChange={(e) => setMask("current_ability", e.currentTarget.checked)}
          label={t("settings.maskCurrent")}
        />
        <Checkbox
          checked={draft.masking.hidden_attributes}
          onChange={(e) => setMask("hidden_attributes", e.currentTarget.checked)}
          label={t("settings.maskHidden")}
        />
        <Checkbox
          checked={draft.masking.personality}
          onChange={(e) => setMask("personality", e.currentTarget.checked)}
          label={t("settings.maskPersonality")}
        />
      </Section>

      <Section title={t("settings.ai")}>
        <AiSettings ai={draft.ai} onChange={(ai) => set("ai", ai)} />
      </Section>

      <Section title={t("settings.about")}>
        <Table>
          <Table.Tbody>
            <Table.Tr>
              <Table.Td>{t("settings.version")}</Table.Td>
              <Table.Td>{info.version}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td>{t("settings.dataDir")}</Table.Td>
              <Table.Td>{info.data_dir}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td>{t("settings.portable")}</Table.Td>
              <Table.Td>{info.portable ? t("settings.yes") : t("settings.no")}</Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </Section>
    </Stack>
  );
}
