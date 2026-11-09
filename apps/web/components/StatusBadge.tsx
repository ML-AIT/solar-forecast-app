import { type Forecast } from "@/lib/api";
import styles from "./StatusBadge.module.css";

export type StatusType = "ready" | "stale" | "fallback" | "missing" | "error";

type StatusBadgeProps = {
  status: StatusType;
  /** The forecast's mode; a fallback badge names it. */
  mode?: Forecast["forecast_mode"];
};

export const STATUS_CONFIG: Record<
  StatusType,
  { label: string; symbol: string; variant: "ok" | "warn" | "bad" }
> = {
  ready: { label: "Forecast ready", symbol: "●", variant: "ok" },
  stale: { label: "Stale", symbol: "⚠", variant: "warn" },
  fallback: { label: "Fallback model", symbol: "⚠", variant: "warn" },
  missing: { label: "No forecast", symbol: "✖", variant: "bad" },
  error: { label: "Error", symbol: "✖", variant: "bad" },
};

// Names the fallback, so the dashboard shows which one the forecast used (apps/api/README.md).
const FALLBACK_LABELS: Record<string, string> = {
  cached_weather: "Fallback: cached weather",
  climatology: "Fallback: climatology",
  baseline: "Fallback: baseline",
};

/** Badge text: the status label, or the named fallback mode. */
export function statusLabel(status: StatusType, mode?: Forecast["forecast_mode"]): string {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error;
  return (status === "fallback" && mode && FALLBACK_LABELS[mode]) || config.label;
}

export default function StatusBadge({ status, mode }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error;

  return (
    <span className={`${styles.badge} ${styles[config.variant]}`}>
      <span className={styles.symbol} aria-hidden="true">
        {config.symbol}
      </span>
      <span>{statusLabel(status, mode)}</span>
    </span>
  );
}

