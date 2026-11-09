"use client";

import { useEffect, useState, useTransition } from "react";
import {
  API_BASE_URL,
  ApiError,
  getForecast,
  getHealth,
  getPlants,
  type Plant,
} from "@/lib/api";
import {
  formatDateTime,
  formatEnergy,
  tomorrowInBangkok,
} from "@/lib/format";
import Alert from "./Alert";
import Header from "./Header";
import OverviewKpis from "./OverviewKpis";
import StationCard, { type PlantForecastState } from "./StationCard";
import styles from "./OverviewDashboard.module.css";

type ApiStatus = "checking" | "online" | "offline";
const HEALTH_POLL_MS = 60_000;

function formatDisplayDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  const dateObj = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(dateObj);
}

export default function OverviewDashboard() {
  const targetDate = tomorrowInBangkok();

  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [plantsState, setPlantsState] = useState<PlantForecastState[]>([]);
  const [loading, setLoading] = useState(true);
  const [plantsError, setPlantsError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  // 1) Health polling
  useEffect(() => {
    let cancelled = false;
    const check = () =>
      getHealth()
        .then((h) => {
          if (!cancelled) setApiStatus(h.status === "ok" ? "online" : "offline");
        })
        .catch(() => {
          if (!cancelled) setApiStatus("offline");
        });

    check();
    const timer = setInterval(check, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // 2) Load plants and parallel forecasts
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setPlantsError(null);

      let plants: Plant[];
      try {
        plants = await getPlants();
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err);
          setPlantsError(msg);
          setLoading(false);
        }
        return;
      }

      if (cancelled) return;

      // Initialize states for all plants
      const initialStates: PlantForecastState[] = plants.map((plant) => ({ plant }));
      setPlantsState(initialStates);

      // Fetch tomorrow's forecast for each plant in parallel (O1, O6 resilience)
      await Promise.all(
        plants.map(async (plant) => {
          try {
            const forecast = await getForecast(plant.id, targetDate);
            if (!cancelled) {
              startTransition(() => {
                setPlantsState((prev) =>
                  prev.map((item) =>
                    item.plant.id === plant.id ? { plant, forecast } : item
                  )
                );
              });
            }
          } catch (err) {
            if (!cancelled) {
              const statusCode = err instanceof ApiError ? err.status : undefined;
              const errorMsg = err instanceof Error ? err.message : String(err);
              startTransition(() => {
                setPlantsState((prev) =>
                  prev.map((item) =>
                    item.plant.id === plant.id
                      ? { plant, error: errorMsg, statusCode }
                      : item
                  )
                );
              });
            }
          }
        })
      );

      if (!cancelled) {
        setLoading(false);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, [targetDate]);

  // Aggregate KPIs across all plants
  let totalP50EnergyKwh = 0;
  let completePlantsCount = 0;
  let latestIssuedAt: string | null = null;

  for (const item of plantsState) {
    if (item.forecast && item.forecast.points.length === 96) {
      completePlantsCount += 1;
      const hours = (item.forecast.resolution_minutes ?? 15) / 60;
      const plantEnergy = item.forecast.points.reduce((sum, p) => sum + p.p50, 0) * hours;
      totalP50EnergyKwh += plantEnergy;

      if (
        !latestIssuedAt ||
        new Date(item.forecast.issued_at).getTime() > new Date(latestIssuedAt).getTime()
      ) {
        latestIssuedAt = item.forecast.issued_at;
      }
    }
  }

  const formattedEnergy = formatEnergy(totalP50EnergyKwh);
  const formattedIssueTime = latestIssuedAt ? formatDateTime(latestIssuedAt) : "–";
  const dateFormatted = formatDisplayDate(targetDate);

  return (
    <main className={`app-container ${styles.container}`}>
      <Header subtitle={`Forecast for ${dateFormatted}`} />

      {apiStatus === "offline" && (
        <Alert variant="error" title="API is currently offline">
          Could not establish a connection to <code>{API_BASE_URL}</code>. Please check that the API service is running.
        </Alert>
      )}

      {plantsError && apiStatus !== "offline" && (
        <Alert variant="error" title="Could not load plant list">
          {plantsError}
        </Alert>
      )}

      {/* KPI row */}
      <OverviewKpis
        totalEnergyKwh={totalP50EnergyKwh}
        completePlantsCount={completePlantsCount}
        totalPlantsCount={plantsState.length}
        latestIssuedAt={latestIssuedAt}
        formattedEnergy={formattedEnergy}
        formattedIssueTime={formattedIssueTime}
      />

      {/* Station Cards Grid */}
      <section className={styles.stationsSection} aria-label="Monitored solar stations">
        <div className={styles.gridCards}>
          {plantsState.map((state) => (
            <StationCard key={state.plant.id} state={state} />
          ))}
        </div>

        {loading && plantsState.length === 0 && (
          <div className={styles.loadingPlaceholder}>
            <p>Loading stations and day-ahead forecasts…</p>
          </div>
        )}
      </section>
    </main>
  );
}

