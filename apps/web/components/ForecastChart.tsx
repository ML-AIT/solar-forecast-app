"use client";

// A hand-drawn SVG forecast chart: 2px P50 line + shaded P10–P90 uncertainty band.
// Coordinates are in a fixed 800×320 viewBox scaled responsively by SVG CSS.
// Fully supports mouse hover and touch drag interactions on tablets and phones.

import { useCallback, useState } from "react";
import type { ForecastPoint } from "@/lib/api";
import { formatNumber, toHHMM } from "@/lib/format";
import styles from "./ForecastChart.module.css";

const WIDTH = 800;
const HEIGHT = 320;
const PAD = { top: 20, right: 20, bottom: 36, left: 56 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;

type Props = {
  points: ForecastPoint[];
  capacityKw?: number;
};

export default function ForecastChart({ points, capacityKw }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  const updateHoverFromClientX = useCallback(
    (clientX: number, target: SVGSVGElement) => {
      const rect = target.getBoundingClientRect();
      const svgX = ((clientX - rect.left) / rect.width) * WIDTH;
      const i = Math.round(((svgX - PAD.left) / PLOT_W) * (points.length - 1));
      setHover(i >= 0 && i < points.length ? i : null);
    },
    [points.length]
  );

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    updateHoverFromClientX(e.clientX, e.currentTarget);
  };

  const handleTouch = (e: React.TouchEvent<SVGSVGElement>) => {
    if (e.touches.length > 0) {
      updateHoverFromClientX(e.touches[0].clientX, e.currentTarget);
    }
  };

  if (points.length === 0) {
    return <p className={styles.empty}>No forecast points available.</p>;
  }

  // Y-axis goes from 0 to capacity (or highest P90 if that exceeds capacity)
  const maxP90 = Math.max(...points.map((p) => p.p90));
  const yMax = Math.max(capacityKw ?? 0, maxP90, 1);

  // Convert index / kW to SVG coordinates
  const x = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * PLOT_W;
  const y = (kw: number) => PAD.top + PLOT_H - (Math.max(kw, 0) / yMax) * PLOT_H;

  const p50Line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.p50).toFixed(1)}`).join(" ");

  // Band polygon: along P90 left→right, then back along P10 right→left
  const band = [
    ...points.map((p, i) => `${x(i).toFixed(1)},${y(p.p90).toFixed(1)}`),
    ...points.map((p, i) => `${x(i).toFixed(1)},${y(p.p10).toFixed(1)}`).reverse(),
  ].join(" ");

  // 5 horizontal ticks (0%, 25%, 50%, 75%, 100%)
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);

  // X labels every 3 hours (12 × 15-min points) plus final point
  const xTicks = points
    .map((_, i) => i)
    .filter((i) => i % 12 === 0 || i === points.length - 1);

  const h = hover !== null ? points[hover] : null;

  return (
    <div className={styles.wrapper}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label={`Solar day-ahead generation forecast chart: P50 line with P10–P90 uncertainty band up to ${formatNumber(yMax)} kW`}
        tabIndex={0}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
        onTouchStart={handleTouch}
        onTouchMove={handleTouch}
        onTouchEnd={() => setHover(null)}
        onTouchCancel={() => setHover(null)}
      >
        <title>Solar Generation Forecast Chart</title>
        <desc>
          Interactive 15-minute generation profile with median line and 10th to 90th percentile uncertainty band.
        </desc>
        {/* Horizontal grid lines & y-axis labels */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(v)}
              y2={y(v)}
              className={styles.grid}
            />
            <text x={PAD.left - 8} y={y(v)} className={styles.yLabel}>
              {formatNumber(v)}
            </text>
          </g>
        ))}

        {/* X-axis labels (HH:MM) every 3 hours */}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={HEIGHT - 12} className={styles.xLabel}>
            {toHHMM(points[i].timestamp)}
          </text>
        ))}

        {/* Plant capacity reference line */}
        {capacityKw && capacityKw <= yMax ? (
          <g>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(capacityKw)}
              y2={y(capacityKw)}
              className={styles.capacity}
            />
            <text x={WIDTH - PAD.right} y={y(capacityKw) - 6} className={styles.capacityLabel}>
              capacity
            </text>
          </g>
        ) : null}

        {/* P10-P90 Uncertainty band */}
        <polygon points={band} className={styles.band} />

        {/* P50 Median forecast line */}
        <polyline points={p50Line} className={styles.p50} />

        {/* Hover / Touch cursor marker */}
        {h && hover !== null ? (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD.top}
              y2={PAD.top + PLOT_H}
              className={styles.cursor}
            />
            <circle cx={x(hover)} cy={y(h.p50)} r={4} className={styles.dot} />
          </g>
        ) : null}

        {/* Y-axis title */}
        <text
          x={14}
          y={PAD.top + PLOT_H / 2}
          className={styles.axisTitle}
          transform={`rotate(-90 14 ${PAD.top + PLOT_H / 2})`}
        >
          kW
        </text>
      </svg>

      {/* Legend & Hover/Touch readout */}
      <div className={styles.footer}>
        <div className={styles.legends}>
          <span className={styles.legend}>
            <span className={styles.swatchLine} aria-hidden="true" />
            <span>P50 (median)</span>
          </span>
          <span className={styles.legend}>
            <span className={styles.swatchBand} aria-hidden="true" />
            <span>P10–P90 band</span>
          </span>
        </div>

        <div className={styles.readout} role="status" aria-live="polite">
          {h ? (
            <div className={styles.readoutActive}>
              <span className={styles.readoutTime}>{toHHMM(h.timestamp)}</span>
              <span className={styles.readoutMetric}>
                P50: <strong>{formatNumber(h.p50)}</strong> <small>kW</small>
              </span>
              <span className={styles.readoutRange}>
                P10–P90: <strong>{formatNumber(h.p10)}</strong> – <strong>{formatNumber(h.p90)}</strong> <small>kW</small>
              </span>
            </div>
          ) : (
            <span className={styles.readoutIdle}>Hover or touch chart to view point values</span>
          )}
        </div>
      </div>
    </div>
  );
}
