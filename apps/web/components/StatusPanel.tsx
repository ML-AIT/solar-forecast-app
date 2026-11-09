import type { Forecast, Plant } from "@/lib/api";
import {
  formatDateTime,
  formatForecastAge,
  isForecastStale,
} from "@/lib/format";
import Alert from "./Alert";
import StatusBadge, { type StatusType } from "./StatusBadge";
import styles from "./StatusPanel.module.css";

type StatusPanelProps = {
  plant: Plant;
  forecast?: Forecast | null;
  isNotFound?: boolean;
  error?: string | null;
  children?: React.ReactNode; // For download buttons in FE-6
};

export function getForecastStatusBadge(
  forecast?: Forecast | null,
  isNotFound?: boolean,
  error?: string | null
): StatusType {
  if (error) return "error";
  if (isNotFound || !forecast) return "missing";
  if (forecast.forecast_mode && forecast.forecast_mode !== "primary") return "fallback";
  if (isForecastStale(forecast.issued_at)) return "stale";
  return "ready";
}

export default function StatusPanel({
  plant,
  forecast,
  isNotFound,
  error,
  children,
}: StatusPanelProps) {
  const badgeStatus = getForecastStatusBadge(forecast, isNotFound, error);
  const age = forecast?.issued_at ? formatForecastAge(forecast.issued_at) : null;
  const isStale = forecast ? isForecastStale(forecast.issued_at) : false;
  const isShort = Boolean(forecast && forecast.points.length < 96);
  const isFallback = Boolean(forecast?.forecast_mode && forecast.forecast_mode !== "primary");
  const forecastMode = forecast?.forecast_mode ?? "primary";

  const pointCountText = forecast
    ? `${forecast.points.length} × ${forecast.resolution_minutes ?? 15} min`
    : "–";

  return (
    <aside className={styles.panel} aria-label="Forecast status and metadata">
      <div className={styles.panelHeader}>
        <h2 className={styles.title}>Status & Details</h2>
        <StatusBadge status={badgeStatus} />
      </div>

      <div className={styles.infoList}>
        <div className={styles.infoRow}>
          <span className={styles.label}>Station ID</span>
          <span className={styles.value}>{plant.id}</span>
        </div>

        <div className={styles.infoRow}>
          <span className={styles.label}>Forecast Mode</span>
          <span className={styles.value}>
            {forecastMode === "primary" ? "primary" : `fallback (${forecastMode})`}
          </span>
        </div>

        <div className={styles.infoRow}>
          <span className={styles.label}>Model Version</span>
          <span className={styles.value}>{forecast?.model_version ?? "–"}</span>
        </div>

        <div className={styles.infoRow}>
          <span className={styles.label}>Issued At</span>
          <span className={styles.value}>
            {forecast?.issued_at ? formatDateTime(forecast.issued_at) : "–"}
          </span>
        </div>

        {age && (
          <div className={styles.infoRow}>
            <span className={styles.label}>Forecast Age</span>
            <span className={styles.value}>{age}</span>
          </div>
        )}

        <div className={styles.infoRow}>
          <span className={styles.label}>Resolution</span>
          <span className={styles.value}>{pointCountText}</span>
        </div>

        <div className={styles.infoRow}>
          <span className={styles.label}>Time Zone</span>
          <span className={styles.value}>{forecast?.timezone ?? "Asia/Bangkok"}</span>
        </div>
      </div>

      {/* S5 Alerts: missing, stale, fewer than 96 points, fallback */}
      <div className={styles.alertsSection} aria-label="Forecast alerts">
        {isNotFound && (
          <Alert variant="error" title="Missing Forecast">
            No forecast data exists for this station on the selected date.
          </Alert>
        )}

        {error && (
          <Alert variant="error" title="Forecast Error">
            {error}
          </Alert>
        )}

        {isFallback && (
          <Alert variant="warn" title="Fallback Model Active">
            Generated using backup mode ({forecastMode.replace("_", " ")}).
          </Alert>
        )}

        {isStale && (
          <Alert variant="warn" title="Stale Forecast">
            Forecast was issued more than 36 hours ago.
          </Alert>
        )}

        {isShort && (
          <Alert variant="warn" title="Incomplete Profile">
            Forecast contains only {forecast?.points.length} of 96 expected intervals.
          </Alert>
        )}
      </div>

      {children}
    </aside>
  );
}

