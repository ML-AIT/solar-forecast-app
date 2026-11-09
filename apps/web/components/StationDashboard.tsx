"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ApiError,
  getForecast,
  getPlants,
  type Forecast,
  type Plant,
} from "@/lib/api";
import {
  formatDateTime,
  formatForecastAge,
  isValidDateStr,
  tomorrowInBangkok,
} from "@/lib/format";
import ForecastChart from "./ForecastChart";
import StationHeader from "./StationHeader";
import StationKpis from "./StationKpis";
import StatusBadge, { type StatusType } from "./StatusBadge";
import styles from "./StationDashboard.module.css";

export default function StationDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const plantId = searchParams.get("id") ?? "";
  const dateParam = searchParams.get("date");
  const date =
    dateParam && isValidDateStr(dateParam) ? dateParam : tomorrowInBangkok();

  const [plants, setPlants] = useState<Plant[] | null>(null);
  const [plantsLoading, setPlantsLoading] = useState(true);
  const [plantsError, setPlantsError] = useState<string | null>(null);

  // Forecast state keyed by request
  const [forecastState, setForecastState] = useState<{
    key: string;
    forecast?: Forecast;
    isNotFound?: boolean;
    error?: string;
  } | null>(null);

  // 1) Load plant list
  useEffect(() => {
    let cancelled = false;

    getPlants()
      .then((data) => {
        if (!cancelled) {
          setPlants(data);
          setPlantsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPlantsError(err instanceof Error ? err.message : String(err));
          setPlantsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const plant = plants?.find((p) => p.id === plantId);
  const requestKey = `${plant?.id ?? ""}|${date}`;

  // 2) Handle date change
  const handleDateChange = (newDate: string) => {
    const params = new URLSearchParams();
    if (plantId) params.set("id", plantId);
    params.set("date", newDate);
    router.replace(`/station/?${params.toString()}`, { scroll: false });
  };

  // 3) Load forecast for current plant & date
  useEffect(() => {
    if (!plant || !date) return;

    let cancelled = false;

    getForecast(plant.id, date)
      .then((data) => {
        if (!cancelled) {
          setForecastState({ key: requestKey, forecast: data });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setForecastState({ key: requestKey, isNotFound: true });
          } else {
            const errorMsg = err instanceof Error ? err.message : String(err);
            setForecastState({ key: requestKey, error: errorMsg });
          }
        }
      });

    return () => {
      cancelled = true;
    };
  }, [plant, date, requestKey]);

  const isCurrent = forecastState?.key === requestKey;
  const forecast = isCurrent ? forecastState?.forecast : undefined;
  const isForecastNotFound = isCurrent ? Boolean(forecastState?.isNotFound) : false;
  const forecastError = isCurrent ? forecastState?.error : undefined;
  const forecastLoading = Boolean(plant && date) && !isCurrent;

  // Loading plant list
  if (plantsLoading) {
    return (
      <main className={`app-container ${styles.page}`}>
        <div className={styles.stateBox}>
          <p className={styles.stateDesc}>Loading plant information…</p>
        </div>
      </main>
    );
  }

  // Plant error
  if (plantsError) {
    return (
      <main className={`app-container ${styles.page}`}>
        <div className={styles.alertBanner} role="alert">
          <div>
            <strong>Error loading plants:</strong> {plantsError}
          </div>
        </div>
      </main>
    );
  }

  // Requirement S1: If ID is unknown or missing, show "Station not found" and link back
  if (!plant) {
    return (
      <main className={`app-container ${styles.page}`}>
        <div className={styles.notFoundContainer}>
          <h1 className={styles.notFoundTitle}>Station not found</h1>
          <p className={styles.notFoundText}>
            {plantId
              ? `No plant exists with identifier "${plantId}".`
              : "No station identifier was specified in the link."}
          </p>
          <Link href="/" className={styles.backButton}>
            ← Back to all stations
          </Link>
        </div>
      </main>
    );
  }

  // Compute status badge
  let badgeStatus: StatusType = "ready";
  if (forecastError) {
    badgeStatus = "error";
  } else if (isForecastNotFound) {
    badgeStatus = "missing";
  } else if (forecast?.forecast_mode && forecast.forecast_mode !== "primary") {
    badgeStatus = "fallback";
  }

  const ageText = forecast?.issued_at
    ? formatForecastAge(forecast.issued_at)
    : null;

  return (
    <main className={`app-container ${styles.page}`}>
      {/* S2: Header with back link, station name, capacity, and date navigation */}
      <StationHeader
        plant={plant}
        date={date}
        onDateChange={handleDateChange}
      />

      {/* S3: KPI row */}
      <StationKpis
        forecast={forecast}
        capacityKw={plant.capacity_kw}
      />

      {/* Main 12-col layout: 8 columns chart + 4 columns status/alerts */}
      <section className={styles.mainGrid} aria-label="Forecast profile and status">
        <div className={styles.chartColumn}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2 className={styles.cardTitle}>Day-Ahead Generation Profile</h2>
              <StatusBadge status={badgeStatus} />
            </div>

            {/* S8: Designed loading, empty, and error states */}
            {forecastLoading && (
              <div className={styles.stateBox} aria-live="polite">
                <p className={styles.stateDesc}>Loading 15-minute forecast…</p>
              </div>
            )}

            {!forecastLoading && isForecastNotFound && (
              <div className={styles.stateBox} role="status">
                <span className={styles.stateIcon} aria-hidden="true">
                  ✖
                </span>
                <h3 className={styles.stateTitle}>No forecast for this date</h3>
                <p className={styles.stateDesc}>
                  No day-ahead generation forecast is available for {plant.name} on {date}.
                </p>
              </div>
            )}

            {!forecastLoading && forecastError && (
              <div className={styles.alertBanner} role="alert">
                <span aria-hidden="true">✖</span>
                <div>
                  <strong>Failed to load forecast:</strong> {forecastError}
                </div>
              </div>
            )}

            {!forecastLoading && forecast && (
              <ForecastChart
                points={forecast.points}
                capacityKw={plant.capacity_kw}
              />
            )}
          </div>
        </div>

        {/* 4-col side panel (FE-5 will expand, FE-3 provides structure) */}
        <aside className={styles.sideColumn} aria-label="Forecast metadata">
          <div className={styles.card}>
            <h2 className={styles.cardTitle}>Forecast Details</h2>
            <div className={styles.infoList}>
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Station ID</span>
                <span className={styles.infoValue}>{plant.id}</span>
              </div>
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Model Version</span>
                <span className={styles.infoValue}>
                  {forecast?.model_version ?? "–"}
                </span>
              </div>
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Issued At</span>
                <span className={styles.infoValue}>
                  {forecast?.issued_at ? formatDateTime(forecast.issued_at) : "–"}
                </span>
              </div>
              {ageText && (
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Forecast Age</span>
                  <span className={styles.infoValue}>{ageText}</span>
                </div>
              )}
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Points</span>
                <span className={styles.infoValue}>
                  {forecast?.points ? `${forecast.points.length} × 15 min` : "–"}
                </span>
              </div>
              <div className={styles.infoRow}>
                <span className={styles.infoLabel}>Time Zone</span>
                <span className={styles.infoValue}>
                  {forecast?.timezone ?? "Asia/Bangkok"}
                </span>
              </div>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}

