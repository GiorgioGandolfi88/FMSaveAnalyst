import { useComputedColorScheme } from "@mantine/core";
import Editor, { loader, type OnMount } from "@monaco-editor/react";
import * as monaco from "monaco-editor/editor/editor.api";
import "monaco-editor/languages/definitions/sql/register";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import { useEffect, useRef } from "react";
import type { Schema } from "../api";

// Bundle Monaco locally: the app must work offline (no CDN).
(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};
loader.config({ monaco });

let completionSchema: Schema | null = null;
let completionRegistered = false;

function registerCompletion() {
  if (completionRegistered) return;
  completionRegistered = true;
  monaco.languages.registerCompletionItemProvider("sql", {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const suggestions: monaco.languages.CompletionItem[] = [];
      for (const o of completionSchema?.objects ?? []) {
        suggestions.push({
          label: o.name,
          kind: monaco.languages.CompletionItemKind.Struct,
          insertText: o.name,
          detail: o.group,
          range,
        });
      }
      const seen = new Set<string>();
      for (const o of completionSchema?.objects ?? []) {
        for (const c of o.columns) {
          if (seen.has(c.name)) continue;
          seen.add(c.name);
          suggestions.push({
            label: c.name,
            kind: monaco.languages.CompletionItemKind.Field,
            insertText: c.name,
            detail: c.type,
            range,
          });
        }
      }
      return { suggestions };
    },
  });
}

interface Props {
  value: string;
  onChange?: (v: string) => void;
  onRun?: () => void;
  readOnly?: boolean;
  schema?: Schema | null;
  height?: number | string;
}

export default function SqlEditor({ value, onChange, onRun, readOnly, schema, height = 260 }: Props) {
  const scheme = useComputedColorScheme("light");
  const runRef = useRef(onRun);
  useEffect(() => {
    runRef.current = onRun;
  }, [onRun]);
  useEffect(() => {
    if (schema) completionSchema = schema;
  }, [schema]);

  const mount: OnMount = (editor) => {
    registerCompletion();
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
  };

  return (
    <Editor
      height={height}
      language="sql"
      theme={scheme === "dark" ? "vs-dark" : "vs"}
      value={value}
      onChange={(v) => onChange?.(v ?? "")}
      onMount={mount}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 13,
        scrollBeyondLastLine: false,
        wordWrap: "on",
        automaticLayout: true,
        tabSize: 2,
      }}
    />
  );
}
