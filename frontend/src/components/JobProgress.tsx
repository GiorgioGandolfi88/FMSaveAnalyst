import { Alert, Code, Progress, Stack, Text } from "@mantine/core";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { careersApi, type Job } from "../api";

interface Props {
  job: Job;
  onFinished: (job: Job) => void;
}

/** Polls an import job and shows its progress, then its outcome. */
export default function JobProgress({ job: initial, onFinished }: Props) {
  const { t } = useTranslation();
  const [job, setJob] = useState<Job>(initial);

  useEffect(() => {
    if (job.status !== "running") return;
    const timer = window.setTimeout(async () => {
      try {
        const next = await careersApi.job(job.id);
        setJob(next);
        if (next.status !== "running") onFinished(next);
      } catch {
        setJob({ ...job }); // retry on the next tick
      }
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [job, onFinished]);

  if (job.status === "running") {
    const pct = job.total ? (100 * job.done) / job.total : 0;
    return (
      <Stack gap="xs">
        <Text fw={500}>{t("careers.job.running")}</Text>
        <Progress value={pct} animated striped size="lg" />
        <Text size="sm" c="dimmed">
          {job.total
            ? t("careers.job.reader", { reader: job.reader, done: job.done, total: job.total })
            : t("careers.job.preparing")}{" "}
          · {Math.round(job.elapsed_s)} s
        </Text>
      </Stack>
    );
  }

  if (job.status === "done" && job.result) {
    const r = job.result;
    const skipped = r.readers.filter((x) => x.status !== "ok").map((x) => x.reader);
    return (
      <Stack gap="xs">
        <Alert color="teal" title={t("careers.job.done", { seconds: Math.round(r.seconds) })}>
          {r.file_name} · {r.game_date}
        </Alert>
        {r.reference_version ? (
          <Text size="sm">
            {t(r.reference_exact ? "careers.job.refUsed" : "careers.job.refApprox", {
              version: r.reference_version,
            })}
          </Text>
        ) : (
          <Text size="sm" c="orange">
            {t("careers.job.refMissing")}
          </Text>
        )}
        {skipped.length > 0 && (
          <Text size="sm" c="dimmed">
            {t("careers.job.readersSkipped", { list: skipped.join(", ") })}
          </Text>
        )}
      </Stack>
    );
  }

  return (
    <Alert
      color={job.status === "rejected" ? "orange" : "red"}
      title={t(job.status === "rejected" ? "careers.job.rejected" : "careers.job.failed")}
    >
      <Code block>{job.message}</Code>
    </Alert>
  );
}
