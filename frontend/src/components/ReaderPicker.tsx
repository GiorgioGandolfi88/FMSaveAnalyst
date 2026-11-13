import { Anchor, Checkbox, Collapse, Group, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { careersApi } from "../api";

interface Props {
  /** selected readers; null = everything */
  value: string[] | null;
  onChange: (value: string[] | null) => void;
}

/** Which data of a save to import: groups of readers, single readers under "advanced". */
export default function ReaderPicker({ value, onChange }: Props) {
  const { t } = useTranslation();
  const [groups, setGroups] = useState<Record<string, string[]> | null>(null);
  const [advanced, setAdvanced] = useState(false);

  useEffect(() => {
    careersApi.importGroups().then(setGroups).catch(() => setGroups({}));
  }, []);

  if (!groups) return null;
  const all = Object.values(groups).flat();
  const selected = new Set(value ?? all);
  const emit = (next: Set<string>) =>
    onChange(all.every((r) => next.has(r)) ? null : all.filter((r) => next.has(r)));

  const toggleGroup = (readers: string[], on: boolean) => {
    const next = new Set(selected);
    for (const r of readers) {
      if (on) next.add(r);
      else next.delete(r);
    }
    emit(next);
  };
  const toggleReader = (reader: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(reader);
    else next.delete(reader);
    emit(next);
  };

  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Group justify="space-between">
          <Text size="sm" fw={600}>
            {t("careers.readers.title")}
          </Text>
          <Group gap="sm">
            <Anchor size="xs" onClick={() => onChange(null)}>
              {t("careers.readers.all")}
            </Anchor>
            <Anchor size="xs" onClick={() => setAdvanced((a) => !a)}>
              {advanced ? t("careers.readers.simple") : t("careers.readers.advanced")}
            </Anchor>
          </Group>
        </Group>
        <SimpleGrid cols={2} spacing="xs">
          {Object.entries(groups).map(([group, readers]) => {
            const on = readers.filter((r) => selected.has(r)).length;
            return (
              <Checkbox
                key={group}
                checked={on === readers.length}
                indeterminate={on > 0 && on < readers.length}
                onChange={(e) => toggleGroup(readers, e.currentTarget.checked)}
                label={t(`careers.readers.groups.${group}`)}
                description={readers.join(", ")}
              />
            );
          })}
        </SimpleGrid>
        <Collapse expanded={advanced}>
          <SimpleGrid cols={3} spacing={4} mt="xs">
            {all.map((r) => (
              <Checkbox
                key={r}
                size="xs"
                checked={selected.has(r)}
                onChange={(e) => toggleReader(r, e.currentTarget.checked)}
                label={r}
              />
            ))}
          </SimpleGrid>
        </Collapse>
        {selected.size === 0 && (
          <Text size="xs" c="red">
            {t("careers.readers.none")}
          </Text>
        )}
        {value !== null && selected.size > 0 && (
          <Text size="xs" c="dimmed">
            {t("careers.readers.partial", { n: selected.size, total: all.length })}
          </Text>
        )}
      </Stack>
    </Paper>
  );
}
