import { Alert, Button, Collapse, Group, Text } from "@mantine/core";
import { IconDownload } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import { openExternal, updatesApi, type UpdateInfo } from "../api";

const DISMISS_KEY = "fmsa.dismissedUpdate";

/** Shown at startup when GitHub has a newer release (if update checks are enabled). */
export default function UpdateBanner({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation();
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [notes, setNotes] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    updatesApi.check().then(setInfo).catch(() => setInfo(null));
  }, [enabled]);

  if (!info?.update_available || !info.latest) return null;
  if (localStorage.getItem(DISMISS_KEY) === info.latest) return null;

  return (
    <Alert color="teal" mb="md" title={t("updates.available", { version: info.latest })}>
      <Text size="sm">{t("updates.body", { current: info.current })}</Text>
      <Group gap="xs" mt="xs">
        <Button size="xs" leftSection={<IconDownload size={14} />}
          onClick={() => openExternal(info.url ?? "")}>
          {t("updates.download")}
        </Button>
        {info.notes && (
          <Button size="xs" variant="default" onClick={() => setNotes((v) => !v)}>
            {t("updates.notes")}
          </Button>
        )}
        <Button size="xs" variant="subtle" color="gray" onClick={() => {
          localStorage.setItem(DISMISS_KEY, info.latest ?? "");
          setInfo(null);
        }}>
          {t("updates.later")}
        </Button>
      </Group>
      <Collapse expanded={notes}>
        <div className="ai-markdown" style={{ marginTop: 8 }}>
          <Markdown>{info.notes ?? ""}</Markdown>
        </div>
      </Collapse>
    </Alert>
  );
}
