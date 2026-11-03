import Link from "next/link";
import { type Forecast, type Plant } from "@/lib/api";
import {
  formatDateTime,
  formatEnergy,
  formatForecastAge,
  formatNumber,
  isForecastStale,
} from "@/lib/format";
import Sparkline from "./Sparkline";
import StatusBadge, { type StatusType } from "./StatusBadge";
import styles from "./StationCard.module.css";

export type PlantForecastState = {
  plant: Plant;
  forecast?: Forecast;
  error?: string;
  statusCode?: number;
};

type StationCardProps = {
  state: PlantForecastState;
};

export function getStationStatus(state: PlantForecastState): StatusType {
  const { forecast, error, statusCode } = state;

  // Order: Error > No forecast > Fallback > Stale > Ready
  if (statusCode === 404) {
    return "missing";
  }
  if (error || !forecast) {
    return "error";
  }
  if (forecast.forecast_mode && forecast.forecast_mode !== "primary") {
    return "fallback";
  }
  if (isForecastStale(forecast.issued_at)) {
    return "stale";
  }
  return "ready";
}

export default function StationCard({ state }: StationCardProps) {
  const { plant, forecast } = state;
  const status = getStationStatus(state);

  // Energy & Peak calculation
  let energyStr = "–";
  let peakStr = "–";
  let sparklineData: number[] = [];
  let ageOrTime = "";

  if (forecast && forecast.points.length > 0) {
    const hours = (forecast.resolution_minutes ?? 15) / 60;
    const totalKwh = forecast.points.reduce((sum, p) => sum + p.p50, 0) * hours;
    const formattedEnergy = formatEnergy(totalKwh);
    energyStr = `${formattedEnergy.value} ${formattedEnergy.unit}`;

    const peakKw = Math.max(...forecast.points.map((p) => p.p50));
    peakStr = `${formatNumber(peakKw)} kW`;

    sparklineData = forecast.points.map((p) => p.p50);

    const age = formatForecastAge(forecast.issued_at);
    if (age) {
      ageOrTime = `Issued ${age}`;
    } else {
      ageOrTime = `Issued ${formatDateTime(forecast.issued_at)}`;
    }
  }

  return (
    <Link
      href={`/station/?id=${encodeURIComponent(plant.id)}`}
      className={styles.card}
      aria-label={`${plant.name}, status ${status}`}
    >
      <div className={styles.topRow}>
        <div className={styles.headerInfo}>
          <span className={styles.plantId}>{plant.id}</span>
          <h2 className={styles.plantName}>{plant.name}</h2>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className={styles.sparklineArea}>
        {forecast ? (
          <Sparkline
            data={sparklineData}
            maxVal={plant.capacity_kw}
            ariaLabel={`24h forecast sparkline for ${plant.name}`}
          />
        ) : (
          <div className={styles.noForecastPlaceholder}>
            <span>{status === "missing" ? "No forecast available" : "Forecast unavailable"}</span>
          </div>
        )}
      </div>

      <div className={styles.metricsRow}>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>P50 Energy</span>
          <span className={styles.metricValue}>{energyStr}</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Peak</span>
          <span className={styles.metricValue}>{peakStr}</span>
        </div>
      </div>

      <div className={styles.bottomRow}>
        <span className={styles.capacity}>
          Cap <strong>{formatNumber(plant.capacity_kw)}</strong> kW
        </span>
        {ageOrTime && <span className={styles.age}>{ageOrTime}</span>}
      </div>
    </Link>
  );
}

