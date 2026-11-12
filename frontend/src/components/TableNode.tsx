import { ActionIcon, Checkbox, Group, Paper, ScrollArea, Stack, Text, TextInput } from "@mantine/core";
import { IconX } from "@tabler/icons-react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { SchemaColumn } from "../api";

export type TableNodeData = {
  alias: string;
  table: string;
  columns: SchemaColumn[];
  selected: string[];
  onToggle: (alias: string, column: string) => void;
  onRemove: (alias: string) => void;
};

export type TableNodeType = Node<TableNodeData, "table">;

export default function TableNode({ data }: NodeProps<TableNodeType>) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");
  const shown = data.columns.filter(
    (c) => !c.internal && c.name.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  return (
    <Paper withBorder shadow="sm" w={250} style={{ overflow: "hidden" }}>
      <Handle type="target" position={Position.Left} style={{ width: 10, height: 10 }} />
      <Group
        justify="space-between"
        px="xs"
        py={4}
        bg="var(--mantine-primary-color-light)"
        className="drag-handle"
        style={{ cursor: "move" }}
      >
        <Text size="sm" fw={700} truncate>
          {data.table} <Text span c="dimmed" size="xs">({data.alias})</Text>
        </Text>
        <ActionIcon size="xs" variant="subtle" color="gray" onClick={() => data.onRemove(data.alias)}>
          <IconX size={12} />
        </ActionIcon>
      </Group>
      <Stack gap={4} p={6}>
        <TextInput
          size="xs"
          placeholder={t("query.filterColumns")}
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
          className="nodrag"
        />
        <ScrollArea.Autosize mah={220} className="nodrag nowheel">
          <Stack gap={2}>
            {shown.map((c) => (
              <Checkbox
                key={c.name}
                size="xs"
                label={c.masked ? `🔒 ${c.name}` : c.name}
                checked={data.selected.includes(c.name)}
                onChange={() => data.onToggle(data.alias, c.name)}
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Stack>
      <Handle type="source" position={Position.Right} style={{ width: 10, height: 10 }} />
    </Paper>
  );
}
