"use client";

// A small hand-drawn SVG chart: p50 line + shaded p10–p90 band over the day.
// No chart library needed. Coordinates are in a fixed 800×320 "viewBox" that
// the browser scales to the container width.

import { useState } from "react";
import type { ForecastPoint } from "@/lib/api";
import { formatNumber, toHHMM } from "@/lib/format";
import styles from "./ForecastChart.module.css";

const WIDTH = 800;
const HEIGHT = 320;
const PAD = { top: 16, right: 16, bottom: 32, left: 56 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;

type Props = {
  points: ForecastPoint[];
  capacityKw?: number;
};

export default function ForecastChart({ points, capacityKw }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  if (points.length === 0) {
    return <p className={styles.empty}>No forecast points.</p>;
  }

  // Y axis goes from 0 to capacity (or the highest p90 if that is larger).
  const maxP90 = Math.max(...points.map((p) => p.p90));
  const yMax = Math.max(capacityKw ?? 0, maxP90, 1) * 1.05;

  // Convert data index / kW to SVG pixel coordinates.
  const x = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * PLOT_W;
  const y = (kw: number) => PAD.top + PLOT_H - (Math.max(kw, 0) / yMax) * PLOT_H;

  const p50Line = points.map((p, i) => `${x(i)},${y(p.p50)}`).join(" ");
  // Band polygon: along p90 left→right, then back along p10 right→left.
  const band = [
    ...points.map((p, i) => `${x(i)},${y(p.p90)}`),
    ...points.map((p, i) => `${x(i)},${y(p.p10)}`).reverse(),
  ].join(" ");

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  // One x label every 3 hours (12 × 15 min) plus the last point.
  const xTicks = points
    .map((_, i) => i)
    .filter((i) => i % 12 === 0 || i === points.length - 1);

  function handleMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const i = Math.round(((svgX - PAD.left) / PLOT_W) * (points.length - 1));
    setHover(i >= 0 && i < points.length ? i : null);
  }

  const h = hover !== null ? points[hover] : null;

  return (
    <div className={styles.wrapper}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label="Forecast power over the day: median with 10–90 percent band"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* Horizontal grid lines + y labels */}
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(v)} y2={y(v)} className={styles.grid} />
            <text x={PAD.left - 8} y={y(v)} className={styles.yLabel}>
              {formatNumber(v)}
            </text>
          </g>
        ))}

        {/* X labels (HH:MM) */}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={HEIGHT - 10} className={styles.xLabel}>
            {toHHMM(points[i].timestamp)}
          </text>
        ))}

        {/* Plant capacity reference line */}
        {capacityKw ? (
          <g>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(capacityKw)} y2={y(capacityKw)} className={styles.capacity} />
            <text x={WIDTH - PAD.right} y={y(capacityKw) - 4} className={styles.capacityLabel}>
              capacity
            </text>
          </g>
        ) : null}

        <polygon points={band} className={styles.band} />
        <polyline points={p50Line} className={styles.p50} />

        {/* Hover marker */}
        {h && hover !== null ? (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + PLOT_H} className={styles.cursor} />
            <circle cx={x(hover)} cy={y(h.p50)} r={4} className={styles.dot} />
          </g>
        ) : null}

        <text x={14} y={PAD.top + PLOT_H / 2} className={styles.axisTitle} transform={`rotate(-90 14 ${PAD.top + PLOT_H / 2})`}>
          kW
        </text>
      </svg>

      <div className={styles.footer}>
        <span className={styles.legend}>
          <span className={styles.swatchLine} /> P50 (median)
        </span>
        <span className={styles.legend}>
          <span className={styles.swatchBand} /> P10–P90 range
        </span>
        <span className={styles.readout}>
          {h
            ? `${toHHMM(h.timestamp)}  P50 ${formatNumber(h.p50)} kW  (P10 ${formatNumber(h.p10)} – P90 ${formatNumber(h.p90)})`
            : "Hover the chart to see values"}
        </span>
      </div>
    </div>
  );
}
