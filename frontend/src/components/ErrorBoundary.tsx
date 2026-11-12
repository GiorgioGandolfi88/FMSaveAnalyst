import { Alert, Button, Code, Group, Stack, Text } from "@mantine/core";
import { Component, type ErrorInfo, type ReactNode } from "react";
import i18n from "../i18n";

interface State {
  error: Error | null;
}

/** Keeps one broken page from blanking the whole window. */
export default class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI error", error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: string }): void {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <Alert color="red" title={i18n.t("app.uiErrorTitle")}>
        <Stack gap="xs">
          <Text size="sm">{i18n.t("app.uiErrorBody")}</Text>
          <Code block>{error.message}</Code>
          <Group>
            <Button size="xs" onClick={() => this.setState({ error: null })}>
              {i18n.t("app.retry")}
            </Button>
            <Button size="xs" variant="default" onClick={() => window.location.reload()}>
              {i18n.t("app.reload")}
            </Button>
          </Group>
        </Stack>
      </Alert>
    );
  }
}
