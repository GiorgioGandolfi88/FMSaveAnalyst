import { Button, Group, Select, Stack, Text, TextInput } from "@mantine/core";
import { IconFolderOpen } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { careersApi, desktopApi, type SaveFile } from "../api";

interface Props {
  value: string;
  onChange: (path: string, save?: SaveFile) => void;
}

/** Choose a Football Manager save: list of the save folder, native dialog, or a pasted path. */
export default function SavePicker({ value, onChange }: Props) {
  const { t } = useTranslation();
  const [saves, setSaves] = useState<SaveFile[]>([]);
  const [folder, setFolder] = useState("");
  const desktop = desktopApi();

  useEffect(() => {
    careersApi
      .saves()
      .then((r) => {
        setSaves(r.saves);
        setFolder(r.folder);
      })
      .catch(() => setSaves([]));
  }, []);

  const browse = async () => {
    const picked = await desktop?.pick_save(folder);
    if (picked) onChange(picked);
  };

  return (
    <Stack gap="xs">
      <Group align="flex-end" gap="xs" wrap="nowrap">
        <Select
          style={{ flex: 1 }}
          label={t("careers.save")}
          placeholder={t("careers.savePlaceholder")}
          searchable
          clearable
          value={saves.some((s) => s.path === value) ? value : null}
          onChange={(v) => v && onChange(v, saves.find((s) => s.path === v))}
          data={saves.map((s) => ({
            value: s.path,
            label: `${s.name}  ·  ${s.modified.replace("T", " ")}  ·  ${s.size_mb} MB`,
          }))}
          nothingFoundMessage="—"
        />
        {desktop && (
          <Button variant="default" leftSection={<IconFolderOpen size={16} />} onClick={browse}>
            {t("careers.browse")}
          </Button>
        )}
      </Group>
      {saves.length === 0 && (
        <Text size="xs" c="dimmed">
          {t("careers.noSaves", { folder: folder || "—" })}
        </Text>
      )}
      <TextInput
        size="xs"
        label={t("careers.manualPath")}
        value={value}
        onChange={(e) => onChange(e.currentTarget.value)}
      />
    </Stack>
  );
}
