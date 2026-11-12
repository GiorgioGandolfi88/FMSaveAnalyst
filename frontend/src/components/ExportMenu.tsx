import { Button, Menu } from "@mantine/core";
import { IconDownload } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { exportData, type BrowseRequest, type ExportFormat } from "../api";

interface Props {
  source: { sql?: string; browse?: BrowseRequest } | null;
  baseName: string;
  onResult: (message: string, ok: boolean) => void;
}

/** CSV / Excel CSV / JSON export of the full result (not just the visible page). */
export default function ExportMenu({ source, baseName, onResult }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);

  const run = async (format: ExportFormat) => {
    if (!source) return;
    setBusy(true);
    try {
      const where = await exportData(source, format, baseName);
      if (where) onResult(t("export.done", { path: where }), true);
    } catch (e) {
      onResult(`${t("export.failed")}: ${String(e)}`, false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button
          variant="default"
          leftSection={<IconDownload size={16} />}
          loading={busy}
          disabled={!source}
        >
          {t("export.button")}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item onClick={() => run("csv_excel")}>{t("export.csvExcel")}</Menu.Item>
        <Menu.Item onClick={() => run("csv")}>{t("export.csv")}</Menu.Item>
        <Menu.Item onClick={() => run("json")}>{t("export.json")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
