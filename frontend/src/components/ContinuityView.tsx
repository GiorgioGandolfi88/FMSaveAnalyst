import { Alert, Group, List, Text, ThemeIcon } from "@mantine/core";
import {
  IconAlertTriangle,
  IconCheck,
  IconMinus,
  IconX,
  type Icon,
} from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import type { ContinuityCheck, ContinuityReport } from "../api";

const VERDICT_COLOR = {
  same: "teal",
  uncertain: "yellow",
  different: "orange",
  incompatible: "red",
} as const;

const OUTCOME: Record<ContinuityCheck["outcome"], { color: string; icon: Icon }> = {
  pass: { color: "teal", icon: IconCheck },
  warn: { color: "yellow", icon: IconAlertTriangle },
  fail: { color: "red", icon: IconX },
  skip: { color: "gray", icon: IconMinus },
};

export default function ContinuityView({ report }: { report: ContinuityReport }) {
  const { t } = useTranslation();
  return (
    <>
      <Alert color={VERDICT_COLOR[report.verdict]} title={t(`careers.verdict.${report.verdict}`)}>
        <Text size="sm">
          {report.save_file} · {report.save_game} {report.save_build} · {report.save_date}
        </Text>
      </Alert>
      {report.gap_warning && (
        <Alert color="yellow" icon={<IconAlertTriangle size={18} />}>
          {t("careers.gap")}
        </Alert>
      )}
      <List spacing={4} size="sm" center>
        {report.checks.map((c) => {
          const o = OUTCOME[c.outcome];
          const I = o.icon;
          return (
            <List.Item
              key={c.id}
              icon={
                <ThemeIcon color={o.color} size={20} radius="xl">
                  <I size={13} />
                </ThemeIcon>
              }
            >
              <Group gap={6}>
                <Text size="sm">{t(`careers.checks.${c.id}`, c.id)}</Text>
                {c.detail && (
                  <Text size="xs" c="dimmed">
                    ({c.detail})
                  </Text>
                )}
              </Group>
            </List.Item>
          );
        })}
      </List>
    </>
  );
}
