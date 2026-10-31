import styles from "./StatusBadge.module.css";

export type StatusType = "ready" | "stale" | "fallback" | "missing" | "error";

type StatusBadgeProps = {
  status: StatusType;
};

const STATUS_CONFIG: Record<
  StatusType,
  { label: string; symbol: string; variant: "ok" | "warn" | "bad" }
> = {
  ready: { label: "Forecast ready", symbol: "●", variant: "ok" },
  stale: { label: "Stale", symbol: "⚠", variant: "warn" },
  fallback: { label: "Fallback model", symbol: "⚠", variant: "warn" },
  missing: { label: "No forecast", symbol: "✖", variant: "bad" },
  error: { label: "Error", symbol: "✖", variant: "bad" },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error;

  return (
    <span className={`${styles.badge} ${styles[config.variant]}`}>
      <span className={styles.symbol} aria-hidden="true">
        {config.symbol}
      </span>
      <span>{config.label}</span>
    </span>
  );
}

