"use client";

import Link from "next/link";
import { type Plant } from "@/lib/api";
import { formatNumber, shiftDate } from "@/lib/format";
import styles from "./StationHeader.module.css";

type StationHeaderProps = {
  plant: Plant;
  date: string;
  onDateChange: (newDate: string) => void;
};

export default function StationHeader({
  plant,
  date,
  onDateChange,
}: StationHeaderProps) {
  const handlePrevDay = () => {
    onDateChange(shiftDate(date, -1));
  };

  const handleNextDay = () => {
    onDateChange(shiftDate(date, 1));
  };

  return (
    <header className={styles.header}>
      <div className={styles.topBar}>
        <Link href="/" className={styles.backLink}>
          ← All stations
        </Link>
        <span className={styles.timeZoneNote}>All times Asia/Bangkok (UTC+7)</span>
      </div>

      <div className={styles.mainRow}>
        <div className={styles.titleGroup}>
          <h1 className={styles.stationTitle}>{plant.name}</h1>
          <span className={styles.stationCapacity}>
            Capacity: <strong>{formatNumber(plant.capacity_kw)}</strong> kW
          </span>
        </div>

        <nav className={styles.dateNav} aria-label="Forecast date controls">
          <button
            type="button"
            className={styles.navButton}
            onClick={handlePrevDay}
            aria-label="Previous day"
            title="Previous day"
          >
            ◀
          </button>
          <label htmlFor="forecast-date-input" className="sr-only">
            Forecast date
          </label>
          <input
            id="forecast-date-input"
            type="date"
            className={styles.dateInput}
            value={date}
            onChange={(e) => {
              if (e.target.value) {
                onDateChange(e.target.value);
              }
            }}
            aria-label="Forecast date"
          />
          <button
            type="button"
            className={styles.navButton}
            onClick={handleNextDay}
            aria-label="Next day"
            title="Next day"
          >
            ▶
          </button>
        </nav>
      </div>
    </header>
  );
}

