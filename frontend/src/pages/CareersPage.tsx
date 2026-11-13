import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Menu,
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
import {
  IconDots,
  IconFolderOpen,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconTrash,
} from "@tabler/icons-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  careersApi,
  desktopApi,
  type CareerDetail,
  type CareerFile,
  type CareerSummary,
  type ContinuityReport,
  type Job,
} from "../api";
import ContinuityView from "../components/ContinuityView";
import ImportLogModal from "../components/ImportLogModal";
import JobProgress from "../components/JobProgress";
import ReaderPicker from "../components/ReaderPicker";
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
  const [readers, setReaders] = useState<string[] | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);

  const reset = () => {
    setName("");
    setSave("");
    setReaders(null);
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
      setJob(await careersApi.create(name.trim(), save.trim(), readers));
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
            <ReaderPicker value={readers} onChange={setReaders} />
            {error && <Alert color="red">{error}</Alert>}
            <Group justify="flex-end">
              <Button variant="default" onClick={close}>
                {t("careers.cancel")}
              </Button>
              <Button
                disabled={!name.trim() || !save.trim() || readers?.length === 0}
                onClick={start}
              >
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
  const [readers, setReaders] = useState<string[] | null>(career.import_readers);
  const [checking, setChecking] = useState(false);
  const [report, setReport] = useState<ContinuityReport | null>(null);
  const [anyway, setAnyway] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (job && !finished) return;
    setSave("");
    setReaders(career.import_readers);
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
      setJob(await careersApi.importSave(career.path, save.trim(), readers));
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
    report &&
    report.verdict !== "incompatible" &&
    (!needsConfirm || anyway) &&
    !job &&
    readers?.length !== 0;

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
        {!job && <ReaderPicker value={readers} onChange={setReaders} />}
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

// ------------------------------------------------------------------ rename / delete

function RenameCareerModal({ career, onClose, onDone }: {
  career: CareerSummary | null;
  onClose: () => void;
  onDone: (renamed: CareerSummary) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setName(career?.name ?? "");
    setError(null);
  }, [career]);

  const save = async () => {
    if (!career) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await careersApi.rename(career.path, name.trim()));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={career !== null} onClose={onClose} title={t("careers.rename.title")}>
      <Stack>
        <TextInput
          label={t("careers.name")}
          value={name}
          data-autofocus
          onChange={(e) => setName(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) void save();
          }}
        />
        <Text size="xs" c="dimmed">
          {t("careers.rename.hint")}
        </Text>
        {error && <Alert color="red">{error}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t("careers.cancel")}
          </Button>
          <Button loading={busy} disabled={!name.trim()} onClick={save}>
            {t("careers.rename.save")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function DeleteCareerModal({ career, onClose, onDone }: {
  career: CareerSummary | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [files, setFiles] = useState<CareerFile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFiles(null);
    setError(null);
    if (career) {
      careersApi.files(career.path).then(setFiles).catch((e) => setError(String(e)));
    }
  }, [career]);

  const remove = async () => {
    if (!career) return;
    setBusy(true);
    setError(null);
    try {
      await careersApi.remove(career.path);
      onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={career !== null} onClose={onClose} title={t("careers.delete.title")} size="lg">
      <Stack>
        <Text>{t("careers.delete.confirm", { name: career?.name ?? "" })}</Text>
        <Alert color="red" variant="light">
          {t("careers.delete.warning")}
        </Alert>
        {files === null ? (
          <Loader size="sm" />
        ) : (
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              {t("careers.delete.files")}
            </Text>
            {files.map((f) => (
              <Text key={f.path} size="xs" ff="monospace">
                {f.path} ({f.size_mb} MB)
              </Text>
            ))}
          </Stack>
        )}
        {error && <Alert color="red">{error}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t("careers.cancel")}
          </Button>
          <Button color="red" loading={busy} disabled={files === null} onClick={remove}>
            {t("careers.delete.button")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function CareerActions({ onRename, onDelete }: { onRename: () => void; onDelete: () => void }) {
  const { t } = useTranslation();
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon variant="subtle" aria-label={t("careers.actions")}>
          <IconDots size={16} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item leftSection={<IconPencil size={14} />} onClick={onRename}>
          {t("careers.rename.title")}
        </Menu.Item>
        <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={onDelete}>
          {t("careers.delete.title")}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
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
  const [logImport, setLogImport] = useState<number | null>(null);
  const [renaming, setRenaming] = useState<CareerSummary | null>(null);
  const [deleting, setDeleting] = useState<CareerSummary | null>(null);

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
  const afterRename = () => {
    setRenaming(null);
    onCareerChanged();
    load();
  };
  const afterDelete = () => {
    setDeleting(null);
    onCareerChanged();
    load();
  };

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
              <Group gap="xs">
                <Button leftSection={<IconRefresh size={16} />} onClick={() => setUpdateOpen(true)}>
                  {t("careers.update")}
                </Button>
                <CareerActions
                  onRename={() => setRenaming(current)}
                  onDelete={() => setDeleting(current)}
                />
              </Group>
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
                          <Button size="compact-xs" variant="light" onClick={() => setLogImport(i.import_id)}>
                            {t("importLog.button")}
                          </Button>
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
                    <Group gap={4} wrap="nowrap">
                      {isCurrent ? (
                        <Badge>{t("careers.opened")}</Badge>
                      ) : (
                        <Button size="xs" variant="light" onClick={() => open(c.path)}>
                          {t("careers.open")}
                        </Button>
                      )}
                      <CareerActions
                        onRename={() => setRenaming(c)}
                        onDelete={() => setDeleting(c)}
                      />
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      {current && (
        <ImportLogModal careerPath={current.path} importId={logImport} onClose={() => setLogImport(null)} />
      )}
      <RenameCareerModal career={renaming} onClose={() => setRenaming(null)} onDone={afterRename} />
      <DeleteCareerModal career={deleting} onClose={() => setDeleting(null)} onDone={afterDelete} />
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
