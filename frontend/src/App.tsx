import {
  ActionIcon,
  Alert,
  Badge,
  AppShell,
  Group,
  Loader,
  NavLink,
  Text,
  Title,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import {
  IconChartBar,
  IconDatabaseSearch,
  IconHome,
  IconMoon,
  IconRobot,
  IconSettings,
  IconSitemap,
  IconSun,
} from "@tabler/icons-react";
import { useCallback, useEffect, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { api, dataApi, type AppInfo, type Schema, type Settings } from "./api";
import i18n from "./i18n";
import PlaceholderPage from "./pages/PlaceholderPage";
import SettingsPage from "./pages/SettingsPage";
import CareersPage from "./pages/CareersPage";
import ExplorePage from "./pages/ExplorePage";
import QueryPage from "./pages/QueryPage";

type PageKey = "start" | "explore" | "query" | "dashboards" | "ai" | "settings";

const NAV: { key: PageKey; icon: ComponentType<{ size?: number }> }[] = [
  { key: "start", icon: IconHome },
  { key: "explore", icon: IconDatabaseSearch },
  { key: "query", icon: IconSitemap },
  { key: "dashboards", icon: IconChartBar },
  { key: "ai", icon: IconRobot },
  { key: "settings", icon: IconSettings },
];

function careerLabel(path: string): string {
  const file = path.split(/[\\/]/).pop() ?? path;
  return file.replace(/\.fmsa$/i, "");
}

export default function App() {
  const { t } = useTranslation();
  const [page, setPage] = useState<PageKey>("start");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [schema, setSchema] = useState<Schema | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [schemaVersion, setSchemaVersion] = useState(0);
  const [pendingSql, setPendingSql] = useState<string | null>(null);
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme("light");

  useEffect(() => {
    Promise.all([api.getSettings(), api.appInfo()])
      .then(([s, i]) => {
        setSettings(s);
        setInfo(i);
        void i18n.changeLanguage(s.language);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  const reloadSettings = useCallback(() => {
    api.getSettings().then(setSettings).catch((e: unknown) => setError(String(e)));
    setSchemaVersion((v) => v + 1);
  }, []);

  const career = settings?.last_career ?? "";
  const maskingKey = JSON.stringify(settings?.masking ?? null);
  useEffect(() => {
    setSchema(null);
    setSchemaError(null);
    if (!career) return;
    dataApi
      .schema()
      .then(setSchema)
      .catch((e: unknown) => setSchemaError(String(e)));
  }, [career, maskingKey, schemaVersion]);

  const openInQuery = useCallback((sql: string) => {
    setPendingSql(sql);
    setPage("query");
  }, []);
  const clearPendingSql = useCallback(() => setPendingSql(null), []);

  const onSettingsSaved = useCallback((s: Settings) => {
    setSettings(s);
    void i18n.changeLanguage(s.language);
  }, []);

  let content;
  if (error) {
    content = (
      <Alert color="red" title={t("app.backendError")}>
        {error}
      </Alert>
    );
  } else if (!settings || !info) {
    content = <Loader />;
  } else if (page === "start") {
    content = (
      <CareersPage currentPath={settings.last_career} onCareerChanged={reloadSettings} />
    );
  } else if (page === "explore" || page === "query") {
    if (!career) {
      content = <Alert color="gray">{t("explore.noCareer")}</Alert>;
    } else if (schemaError) {
      content = <Alert color="red">{schemaError}</Alert>;
    } else if (!schema) {
      content = <Loader />;
    } else if (page === "explore") {
      content = <ExplorePage key={schema.career} schema={schema} onOpenInQuery={openInQuery} />;
    } else {
      content = (
        <QueryPage
          key={schema.career}
          schema={schema}
          initialSql={pendingSql}
          onInitialSqlUsed={clearPendingSql}
        />
      );
    }
  } else if (page === "settings") {
    content = <SettingsPage settings={settings} info={info} onSaved={onSettingsSaved} />;
  } else {
    content = <PlaceholderPage title={t(`nav.${page}`)} />;
  }

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 230, breakpoint: 0 }} padding="lg">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Title order={4}>{t("app.name")}</Title>
            {settings?.last_career ? (
              <Badge variant="light" size="lg" tt="none">
                {careerLabel(settings.last_career)}
              </Badge>
            ) : (
              <Text size="sm" c="dimmed" visibleFrom="sm">
                {t("app.tagline")}
              </Text>
            )}
          </Group>
          <ActionIcon
            variant="default"
            aria-label="color scheme"
            onClick={() => setColorScheme(scheme === "dark" ? "light" : "dark")}
          >
            {scheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
          </ActionIcon>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {NAV.map(({ key, icon: Icon }) => (
          <NavLink
            key={key}
            active={page === key}
            label={t(`nav.${key}`)}
            leftSection={<Icon size={18} />}
            onClick={() => setPage(key)}
          />
        ))}
        {info && (
          <Text size="xs" c="dimmed" mt="auto" p="xs">
            v{info.version}
          </Text>
        )}
      </AppShell.Navbar>
      <AppShell.Main>{content}</AppShell.Main>
    </AppShell>
  );
}
