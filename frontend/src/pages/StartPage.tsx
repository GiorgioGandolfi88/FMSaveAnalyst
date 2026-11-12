import { Badge, Button, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { IconFolderOpen, IconPlus } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import type { Settings } from "../api";

export default function StartPage({ settings }: { settings: Settings }) {
  const { t } = useTranslation();
  return (
    <Stack maw={960}>
      <Title order={2}>{t("start.title")}</Title>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Card withBorder padding="lg">
          <Stack gap="sm" h="100%">
            <Group gap="xs">
              <IconPlus size={22} />
              <Text fw={600}>{t("start.newCareer")}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {t("start.newCareerDesc")}
            </Text>
            <Button mt="auto" disabled>
              {t("start.newCareer")}
            </Button>
          </Stack>
        </Card>
        <Card withBorder padding="lg">
          <Stack gap="sm" h="100%">
            <Group gap="xs">
              <IconFolderOpen size={22} />
              <Text fw={600}>{t("start.openCareer")}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {t("start.openCareerDesc")}
            </Text>
            <Button mt="auto" variant="light" disabled>
              {t("start.openCareer")}
            </Button>
          </Stack>
        </Card>
      </SimpleGrid>
      <Badge variant="light" color="gray">
        {t("start.comingSoon")}
      </Badge>
      <Title order={4}>{t("start.recent")}</Title>
      {settings.recent_careers.length === 0 ? (
        <Text c="dimmed">{t("start.noRecent")}</Text>
      ) : (
        settings.recent_careers.map((c) => <Text key={c}>{c}</Text>)
      )}
    </Stack>
  );
}
