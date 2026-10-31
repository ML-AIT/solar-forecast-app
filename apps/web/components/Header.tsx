"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, getHealth } from "@/lib/api";
import styles from "./Header.module.css";

type ApiStatus = "checking" | "online" | "offline";

const HEALTH_POLL_MS = 60_000;

type HeaderProps = {
  subtitle?: string;
};

export default function Header({ subtitle }: HeaderProps) {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

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

  const statusLabel =
    apiStatus === "online"
      ? "● API online"
      : apiStatus === "offline"
        ? "✖ API offline"
        : "● Checking…";

  return (
    <header className={styles.header}>
      <div className={styles.titleArea}>
        <h1 className={styles.title}>Solar Day-Ahead Forecast</h1>
        <p className={styles.meta}>
          {subtitle ?? "15-minute PV power forecasts for PEA plants"} · All times Asia/Bangkok (UTC+7)
        </p>
      </div>
      <div
        className={`${styles.statusPill} ${styles[apiStatus]}`}
        title={`API endpoint: ${API_BASE_URL}`}
        role="status"
        aria-live="polite"
      >
        <span className={styles.statusDot} aria-hidden="true" />
        <span>{statusLabel}</span>
      </div>
    </header>
  );
}

