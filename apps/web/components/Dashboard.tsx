"use client";

import { useEffect, useState } from "react";
import {
  API_BASE_URL,
  getForecast,
  getPlants,
  type Forecast,
  type Plant,
} from "@/lib/api";
import { formatDateTime, formatNumber, tomorrowInBangkok } from "@/lib/format";
import ForecastChart from "./ForecastChart";
import Header from "./Header";
import StatTile from "./StatTile";
import styles from "./Dashboard.module.css";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export default function Dashboard() {
  // ---- User selections ----
  const [selectedPlantId, setSelectedPlantId] = useState("");
  const [date, setDate] = useState(tomorrowInBangkok);

  // ---- Data from the API ----
  const [plants, setPlants] = useState<Plant[] | null>(null);
  const [plantsError, setPlantsError] = useState<string | null>(null);
  // Remember WHICH request a result belongs to, so we can tell when the
  // current selection is still loading (result.key !== current key).
  const [result, setResult] = useState<{
    key: string;
    forecast?: Forecast;
    error?: string;
  } | null>(null);

  // Until the user picks a plant, use the first one from the API.
  const plantId = selectedPlantId || plants?.[0]?.id || "";
  const plant = plants?.find((p) => p.id === plantId);
  const requestKey = `${plantId}|${date}`;

  // 1) Plant list: load once.
  useEffect(() => {
    getPlants()
      .then(setPlants)
      .catch((err) => setPlantsError(errorMessage(err)));
  }, []);

  // 3) Forecast: reload whenever plant or date changes.
  useEffect(() => {
    if (!plantId || !date) return;
    let cancelled = false; // ignore late responses after the selection changed
    getForecast(plantId, date)
      .then((forecast) => {
        if (!cancelled) setResult({ key: requestKey, forecast });
      })
      .catch((err) => {
        if (!cancelled) setResult({ key: requestKey, error: errorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [plantId, date, requestKey]);

  const isCurrent = result?.key === requestKey;
  const forecast = isCurrent ? result?.forecast : undefined;
  const forecastError = isCurrent ? result?.error : undefined;
  const loading = Boolean(plantId && date) && !isCurrent;

  // ---- Summary numbers ----
  // Each point is a 15-min average power (kW) → energy per point = kW × 0.25 h.
  const hours = (forecast?.resolution_minutes ?? 15) / 60;
  const energyKwh = forecast ? forecast.points.reduce((sum, p) => sum + p.p50, 0) * hours : null;
  const peakKw = forecast ? Math.max(...forecast.points.map((p) => p.p50)) : null;

  return (
    <main className={`app-container ${styles.page}`}>
      <Header />

      {/* ---- Controls ---- */}
      <section className={styles.controls}>
        <label className={styles.field}>
          <span>Plant</span>
          <select
            value={plantId}
            onChange={(e) => setSelectedPlantId(e.target.value)}
            disabled={!plants || plants.length === 0}
          >
            {!plants && <option value="">Loading plants…</option>}
            {plants?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span>Forecast date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </section>

      {plantsError && (
        <p className={styles.error}>
          Could not load plants from {API_BASE_URL}: {plantsError}
        </p>
      )}

      {/* ---- Summary tiles ---- */}
      <section className={styles.tiles}>
        <StatTile label="Forecast energy (P50)" value={energyKwh} unit="kWh" />
        <StatTile label="Peak power (P50)" value={peakKw} unit="kW" />
        <StatTile label="Plant capacity" value={plant?.capacity_kw ?? null} unit="kW" />
      </section>

      {/* ---- Chart ---- */}
      <section className={styles.card}>
        <h2 className={styles.cardTitle}>
          {plant?.name ?? plantId} · {date}
        </h2>
        {loading && <p className={styles.muted}>Loading forecast…</p>}
        {forecastError && <p className={styles.error}>Could not load forecast: {forecastError}</p>}
        {forecast && <ForecastChart points={forecast.points} capacityKw={plant?.capacity_kw} />}
      </section>

      {/* ---- Metadata ---- */}
      {forecast && (
        <section className={styles.meta}>
          <span>
            Issued: <strong>{formatDateTime(forecast.issued_at)}</strong>
          </span>
          <span>
            Model: <strong>{forecast.model_version}</strong>
          </span>
          <span>
            Points: <strong>{formatNumber(forecast.points.length)}</strong> × {forecast.resolution_minutes} min (
            {forecast.unit}, {forecast.timezone})
          </span>
        </section>
      )}
    </main>
  );
}
