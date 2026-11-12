import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Modal,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconFolderOpen, IconPlus, IconRefresh } from "@tabler/icons-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  careersApi,
  desktopApi,
  type CareerDetail,
  type CareerSummary,
  type ContinuityReport,
  type Job,
} from "../api";
import ContinuityView from "../components/ContinuityView";
import JobProgress from "../components/JobProgress";
import SavePicker from "../components/SavePicker";

interface Props {
  currentPath: string;
  onCareerChanged: () => void;
}

function period(c: { first_game_date: string | null; last_game_date: string | null }) {
  if (!c.first_game_date) return "—";
  return c.first_game_date === c.last_game_date
    ? c.first_game_date
    : `${c.first_game_date} → ${c.last_game_date}`;
}

// ------------------------------------------------------------------ new career

function NewCareerModal({ opened, onClose, onDone }: {
  opened: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [save, setSave] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);

  const reset = () => {
    setName("");
    setSave("");
    setJob(null);
    setError(null);
    setFinished(false);
  };
  const close = () => {
    if (job && !finished) return; // never hide a running import
    reset();
    onClose();
  };
  const start = async () => {
    setError(null);
    try {
      setJob(await careersApi.create(name.trim(), save.trim()));
    } catch (e) {
      setError(String(e));
    }
  };
  const finishedJob = useCallback(
    (j: Job) => {
      setFinished(true);
      if (j.status === "done") onDone();
    },
    [onDone],
  );

  return (
    <Modal opened={opened} onClose={close} title={t("careers.newCareer")} size="lg">
      <Stack>
        {!job ? (
          <>
            <SavePicker
              value={save}
              onChange={(path, s) => {
                setSave(path);
                if (!name && s) setName(s.name);
              }}
            />
            <TextInput
              label={t("careers.name")}
              placeholder={t("careers.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
            />
            {error && <Alert color="red">{error}</Alert>}
            <Group justify="flex-end">
              <Button variant="default" onClick={close}>
                {t("careers.cancel")}
              </Button>
              <Button disabled={!name.trim() || !save.trim()} onClick={start}>
                {t("careers.create")}
              </Button>
            </Group>
          </>
        ) : (
          <>
            <JobProgress job={job} onFinished={finishedJob} />
            {finished && (
              <Group justify="flex-end">
                <Button onClick={close}>{t("careers.close")}</Button>
              </Group>
            )}
          </>
        )}
      </Stack>
    </Modal>
  );
}

// ------------------------------------------------------------------ update career

function UpdateCareerModal({ career, opened, onClose, onDone }: {
  career: CareerSummary;
  opened: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [save, setSave] = useState("");
  const [checking, setChecking] = useState(false);
  const [report, setReport] = useState<ContinuityReport | null>(null);
  const [anyway, setAnyway] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (job && !finished) return;
    setSave("");
    setReport(null);
    setAnyway(false);
    setJob(null);
    setFinished(false);
    setError(null);
    onClose();
  };
  const check = async () => {
    setChecking(true);
    setError(null);
    setReport(null);
    try {
      setReport(await careersApi.check(career.path, save.trim()));
    } catch (e) {
      setError(String(e));
    } finally {
      setChecking(false);
    }
  };
  const start = async () => {
    try {
      setJob(await careersApi.importSave(career.path, save.trim()));
    } catch (e) {
      setError(String(e));
    }
  };
  const finishedJob = useCallback(
    (j: Job) => {
      setFinished(true);
      if (j.status === "done") onDone();
    },
    [onDone],
  );

  const needsConfirm = report && (report.verdict === "uncertain" || report.verdict === "different");
  const canImport =
    report && report.verdict !== "incompatible" && (!needsConfirm || anyway) && !job;

  return (
    <Modal opened={opened} onClose={close} title={`${t("careers.update")} · ${career.name}`} size="lg">
      <Stack>
        {!job && (
          <>
            <SavePicker
              value={save}
              onChange={(p) => {
                setSave(p);
                setReport(null);
                setAnyway(false);
              }}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={check} loading={checking} disabled={!save.trim()}>
                {t("careers.check")}
              </Button>
            </Group>
            {checking && (
              <Text size="sm" c="dimmed">
                {t("careers.checking")}
              </Text>
            )}
          </>
        )}
        {error && <Alert color="red">{error}</Alert>}
        {report && !job && <ContinuityView report={report} />}
        {needsConfirm && !job && (
          <Checkbox
            checked={anyway}
            onChange={(e) => setAnyway(e.currentTarget.checked)}
            label={t("careers.importAnyway")}
          />
        )}
        {job ? (
          <JobProgress job={job} onFinished={finishedJob} />
        ) : (
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              {t("careers.cancel")}
            </Button>
            <Button disabled={!canImport} onClick={start}>
              {t("careers.importNow")}
            </Button>
          </Group>
        )}
        {finished && (
          <Group justify="flex-end">
            <Button onClick={close}>{t("careers.close")}</Button>
          </Group>
        )}
      </Stack>
    </Modal>
  );
}

// ------------------------------------------------------------------ page

export default function CareersPage({ currentPath, onCareerChanged }: Props) {
  const { t } = useTranslation();
  const [careers, setCareers] = useState<CareerSummary[] | null>(null);
  const [detail, setDetail] = useState<CareerDetail | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    careersApi.list().then(setCareers).catch((e) => setError(String(e)));
    if (currentPath) {
      careersApi.detail(currentPath).then(setDetail).catch(() => setDetail(null));
    } else {
      setDetail(null);
    }
  }, [currentPath]);

  useEffect(load, [load]);

  const open = async (path: string) => {
    try {
      await careersApi.open(path);
      onCareerChanged();
    } catch (e) {
      setError(String(e));
    }
  };
  const browseCareer = async () => {
    const picked = await desktopApi()?.pick_career("");
    if (picked) await open(picked);
  };
  const afterImport = useCallback(() => {
    onCareerChanged();
    load();
  }, [onCareerChanged, load]);

  const current = detail?.summary;

  return (
    <Stack maw={1100}>
      <Title order={2}>{t("careers.title")}</Title>
      {error && (
        <Alert color="red" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Card withBorder padding="lg">
          <Stack gap="sm" h="100%">
            <Group gap="xs">
              <IconPlus size={22} />
              <Text fw={600}>{t("careers.newCareer")}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {t("careers.newCareerDesc")}
            </Text>
            <Button mt="auto" onClick={() => setNewOpen(true)}>
              {t("careers.newCareer")}
            </Button>
          </Stack>
        </Card>
        <Card withBorder padding="lg">
          <Stack gap="sm" h="100%">
            <Group gap="xs">
              <IconFolderOpen size={22} />
              <Text fw={600}>{t("careers.openCareer")}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {t("careers.openCareerDesc")}
            </Text>
            <Button
              mt="auto"
              variant="light"
              onClick={browseCareer}
              disabled={!desktopApi()}
            >
              {t("careers.browse")}
            </Button>
          </Stack>
        </Card>
      </SimpleGrid>

      <Paper withBorder p="md">
        <Stack gap="sm">
          <Group justify="space-between">
            <Title order={4}>{t("careers.current")}</Title>
            {current && (
              <Button leftSection={<IconRefresh size={16} />} onClick={() => setUpdateOpen(true)}>
                {t("careers.update")}
              </Button>
            )}
          </Group>
          {!current ? (
            <Text c="dimmed">{t("careers.none")}</Text>
          ) : (
            <>
              <Group gap="lg">
                <Text fw={700} size="lg">
                  {current.name}
                </Text>
                <Badge variant="light">{current.game}</Badge>
                <Text size="sm">
                  {t("careers.period")}: {period(current)}
                </Text>
                {current.manager && (
                  <Text size="sm">
                    {t("careers.manager")}: {current.manager}
                  </Text>
                )}
                <Text size="sm">
                  {t("careers.reference")}:{" "}
                  {current.reference_version ?? t("careers.referenceNone")}
                </Text>
                <Text size="sm" c="dimmed">
                  {current.size_mb} MB
                </Text>
              </Group>
              <Title order={5}>{t("careers.imports")}</Title>
              <Table striped withTableBorder>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>#</Table.Th>
                    <Table.Th>{t("careers.colFile")}</Table.Th>
                    <Table.Th>{t("careers.colGameDate")}</Table.Th>
                    <Table.Th>{t("careers.colImportedAt")}</Table.Th>
                    <Table.Th>{t("careers.colDuration")}</Table.Th>
                    <Table.Th>{t("careers.colStatus")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {detail.imports.map((i) => (
                    <Table.Tr key={i.import_id}>
                      <Table.Td>{i.import_id}</Table.Td>
                      <Table.Td>{i.file_name}</Table.Td>
                      <Table.Td>{i.game_date}</Table.Td>
                      <Table.Td>{i.finished_at?.replace("T", " ")}</Table.Td>
                      <Table.Td>{i.duration_s ? `${Math.round(i.duration_s)} s` : ""}</Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          <Badge color={i.status === "ok" ? "teal" : "red"} variant="light">
                            {i.status}
                          </Badge>
                          {i.skipped_readers.length > 0 && (
                            <Tooltip
                              multiline
                              w={360}
                              label={i.skipped_readers.map((r) => r.reader).join(", ")}
                            >
                              <Badge color="gray" variant="outline">
                                {t("careers.skipped")}: {i.skipped_readers.length}
                              </Badge>
                            </Tooltip>
                          )}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </>
          )}
        </Stack>
      </Paper>

      <Title order={4}>{t("careers.list")}</Title>
      {careers === null ? (
        <Loader />
      ) : careers.length === 0 ? (
        <Text c="dimmed">{t("careers.noCareers")}</Text>
      ) : (
        <Table highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t("careers.colName")}</Table.Th>
              <Table.Th>{t("careers.colGame")}</Table.Th>
              <Table.Th>{t("careers.colPeriod")}</Table.Th>
              <Table.Th>{t("careers.colImports")}</Table.Th>
              <Table.Th>{t("careers.colSize")}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {careers.map((c) => {
              const isCurrent = c.path.toLowerCase() === currentPath.toLowerCase();
              return (
                <Table.Tr key={c.path}>
                  <Table.Td>
                    <Text fw={500}>{c.name}</Text>
                    <Text size="xs" c="dimmed">
                      {c.path}
                    </Text>
                  </Table.Td>
                  <Table.Td>{c.game ?? "—"}</Table.Td>
                  <Table.Td>{period(c)}</Table.Td>
                  <Table.Td>{c.imports}</Table.Td>
                  <Table.Td>{c.size_mb} MB</Table.Td>
                  <Table.Td>
                    {isCurrent ? (
                      <Badge>{t("careers.opened")}</Badge>
                    ) : (
                      <Button size="xs" variant="light" onClick={() => open(c.path)}>
                        {t("careers.open")}
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <NewCareerModal opened={newOpen} onClose={() => setNewOpen(false)} onDone={afterImport} />
      {current && (
        <UpdateCareerModal
          career={current}
          opened={updateOpen}
          onClose={() => setUpdateOpen(false)}
          onDone={afterImport}
        />
      )}
    </Stack>
  );
}
