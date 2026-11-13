import { Tooltip } from "@mantine/core";
import { useCallback, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  /** remembers the height between sessions (localStorage key suffix) */
  id: string;
  defaultHeight: number;
  minHeight?: number;
  children: ReactNode;
}

const KEY = "fmsa.area.";

function stored(id: string, fallback: number): number {
  const v = Number(localStorage.getItem(KEY + id));
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

/** A box whose height the user changes by dragging the bar below it (double click: reset). */
export default function ResizableArea({ id, defaultHeight, minHeight = 80, children }: Props) {
  const { t } = useTranslation();
  const [height, setHeight] = useState(() => stored(id, defaultHeight));
  const drag = useRef<{ y: number; h: number } | null>(null);

  const save = useCallback((h: number) => localStorage.setItem(KEY + id, String(Math.round(h))), [id]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { y: e.clientY, h: height };
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    setHeight(Math.max(minHeight, drag.current.h + e.clientY - drag.current.y));
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    drag.current = null;
    save(height);
  };
  const reset = () => {
    setHeight(defaultHeight);
    localStorage.removeItem(KEY + id);
  };

  return (
    <div>
      <div style={{ height, minHeight }}>{children}</div>
      <Tooltip label={t("common.resizeHint")} openDelay={600} position="bottom">
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label={t("common.resizeHint")}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onDoubleClick={reset}
          style={{
            height: 10,
            cursor: "row-resize",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            touchAction: "none",
          }}
        >
          <div style={{ width: 48, height: 4, borderRadius: 2, background: "var(--mantine-color-default-border)" }} />
        </div>
      </Tooltip>
    </div>
  );
}
