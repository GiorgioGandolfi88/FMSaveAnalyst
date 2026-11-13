import { Alert, Badge, Code, Group, Loader, Modal, ScrollArea, Stack, Table, Text } from "@mantine/core";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { careersApi, type ImportLog } from "../api";

interface Props {
  careerPath: string;
  importId: number | null;
  onClose: () => void;
}

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? "" : n.toLocaleString());
const time = (s: string | null) => (s ? s.slice(11) : "");

/** Detailed per-reader / per-table log of one import. */
export default function ImportLogModal({ careerPath, importId, onClose }: Props) {
  const { t } = useTranslation();
  const [log, setLog] = useState<ImportLog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLog(null);
    setError(null);
    if (importId === null) return;
    careersApi.importLog(careerPath, importId).then(setLog).catch((e) => setError(String(e)));
  }, [careerPath, importId]);

  const totals = log?.rows.reduce(
    (acc, r) => ({ read: acc.read + (r.rows_read ?? 0), inserted: acc.inserted + (r.rows_inserted ?? 0) }),
    { read: 0, inserted: 0 },
  );

  return (
    <Modal opened={importId !== null} onClose={onClose} size="95%" title={t("importLog.title", { id: importId })}>
      {error && <Alert color="red">{error}</Alert>}
      {!log && !error && <Loader />}
      {log && (
        <Stack gap="xs">
          {log.import && (
            <Group gap="lg">
              <Text size="sm">{log.import.file_name}</Text>
              <Text size="sm">{t("importLog.started")}: {log.import.started_at}</Text>
              <Text size="sm">{t("importLog.finished")}: {log.import.finished_at}</Text>
              <Text size="sm">{t("importLog.duration")}: {log.import.duration_s} s</Text>
              {totals && (
                <Text size="sm">
                  {t("importLog.totals", { read: fmt(totals.read), inserted: fmt(totals.inserted) })}
                </Text>
              )}
            </Group>
          )}
          {log.import?.log_file && (
            <Text size="xs" c="dimmed">
              {t("importLog.file")}: <Code>{log.import.log_file}</Code>
            </Text>
          )}
          {log.rows.length === 0 ? (
            <Alert color="gray">{t("importLog.none")}</Alert>
          ) : (
            <ScrollArea h="65vh">
              <Table striped withTableBorder fz="xs" verticalSpacing={2} stickyHeader>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>#</Table.Th>
                    <Table.Th>{t("importLog.reader")}</Table.Th>
                    <Table.Th>{t("importLog.table")}</Table.Th>
                    <Table.Th>{t("importLog.start")}</Table.Th>
                    <Table.Th>{t("importLog.end")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.readMs")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.writeMs")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.rowsRead")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.rowsInserted")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.rowsUpdated")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.rowsUnchanged")}</Table.Th>
                    <Table.Th ta="right">{t("importLog.rowsClosed")}</Table.Th>
                    <Table.Th>{t("importLog.status")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {log.rows.map((r) => {
                    const child = r.storage === "child";
                    return (
                      <Table.Tr key={r.seq}>
                        <Table.Td>{r.seq}</Table.Td>
                        <Table.Td>
                          {!child && (
                            <>
                              <Text span fw={600} size="xs">{r.reader}</Text>{" "}
                              <Text span c="dimmed" size="xs">{r.fmsave_call}</Text>
                            </>
                          )}
                        </Table.Td>
                        <Table.Td>
                          <Text span size="xs" pl={child ? "md" : 0}>{r.table_name}</Text>{" "}
                          <Badge size="xs" variant="outline" color="gray">{r.storage}</Badge>
                        </Table.Td>
                        <Table.Td>{child ? "" : time(r.started_at)}</Table.Td>
                        <Table.Td>{child ? "" : time(r.finished_at)}</Table.Td>
                        <Table.Td ta="right">{child ? "" : fmt(r.read_ms)}</Table.Td>
                        <Table.Td ta="right">{child ? "" : fmt(r.write_ms)}</Table.Td>
                        <Table.Td ta="right">{fmt(r.rows_read)}</Table.Td>
                        <Table.Td ta="right">{fmt(r.rows_inserted)}</Table.Td>
                        <Table.Td ta="right">{fmt(r.rows_updated)}</Table.Td>
                        <Table.Td ta="right">{fmt(r.rows_unchanged)}</Table.Td>
                        <Table.Td ta="right">{fmt(r.rows_closed)}</Table.Td>
                        <Table.Td>
                          {!child && (
                            <Badge size="xs" color={r.status === "ok" ? "teal" : r.status === "unsupported" ? "gray" : "red"}
                              title={r.message ?? undefined}>
                              {r.status}
                            </Badge>
                          )}
                        </Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          )}
        </Stack>
      )}
    </Modal>
  );
}
