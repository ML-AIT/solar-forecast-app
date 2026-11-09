"use client";

import { useState } from "react";
import type { ForecastPoint } from "@/lib/api";
import { formatNumber, toHHMM } from "@/lib/format";
import styles from "./DataTable.module.css";

type DataTableProps = {
  points: ForecastPoint[];
};

export default function DataTable({ points }: DataTableProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (points.length === 0) {
    return null;
  }

  return (
    <section className={styles.container} aria-label="15-minute interval forecast data table">
      <div className={styles.toggleBar}>
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={() => setIsOpen((prev) => !prev)}
          aria-expanded={isOpen}
        >
          <span>{isOpen ? "Hide data table" : `Show data table (${points.length} intervals)`}</span>
          <span aria-hidden="true">{isOpen ? "▲" : "▼"}</span>
        </button>
      </div>

      {isOpen && (
        <div className={styles.card}>
          <div className={styles.tableHeader}>
            <div>
              <h2 className={styles.title}>15-Minute Interval Data</h2>
              <span className={styles.subtitle}>Night intervals (zero generation) are dimmed</span>
            </div>
            <span className={styles.subtitle}>All values in kW</span>
          </div>

          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>Time</th>
                  <th className={`${styles.th} ${styles.thRight}`}>P10 (kW)</th>
                  <th className={`${styles.th} ${styles.thRight}`}>P50 (kW)</th>
                  <th className={`${styles.th} ${styles.thRight}`}>P90 (kW)</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p, idx) => {
                  const isNight = p.p10 === 0 && p.p50 === 0 && p.p90 === 0;
                  return (
                    <tr
                      key={p.timestamp || idx}
                      className={`${styles.tr} ${isNight ? styles.nightRow : ""}`}
                    >
                      <td className={`${styles.td} ${styles.tdMono}`}>
                        {toHHMM(p.timestamp)}
                      </td>
                      <td className={`${styles.td} ${styles.tdRight}`}>
                        {formatNumber(p.p10)}
                      </td>
                      <td className={`${styles.td} ${styles.tdRight}`}>
                        <strong>{formatNumber(p.p50)}</strong>
                      </td>
                      <td className={`${styles.td} ${styles.tdRight}`}>
                        {formatNumber(p.p90)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

