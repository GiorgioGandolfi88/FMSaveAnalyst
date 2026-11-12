import { Paper, Stack, Text, Title } from "@mantine/core";
import { IconTools } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";

export default function PlaceholderPage({ title }: { title: string }) {
  const { t } = useTranslation();
  return (
    <Stack>
      <Title order={2}>{title}</Title>
      <Paper withBorder p="xl">
        <Stack align="center" gap="xs">
          <IconTools size={40} stroke={1.5} />
          <Text fw={600}>{t("placeholder.title")}</Text>
          <Text c="dimmed">{t("placeholder.body")}</Text>
        </Stack>
      </Paper>
    </Stack>
  );
}
