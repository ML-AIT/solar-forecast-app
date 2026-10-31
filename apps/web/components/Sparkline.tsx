import { useId } from "react";
import styles from "./Sparkline.module.css";

type SparklineProps = {
  data: number[];
  maxVal?: number;
  width?: number;
  height?: number;
  ariaLabel?: string;
};

export default function Sparkline({
  data,
  maxVal,
  width = 240,
  height = 56,
  ariaLabel = "P50 power forecast sparkline",
}: SparklineProps) {
  const reactId = useId();
  const gradientId = `sparkline-grad-${reactId.replace(/:/g, "")}`;

  if (!data || data.length < 2) {
    return <div className={styles.empty} style={{ height }} />;
  }

  const max = Math.max(maxVal ?? 0, ...data, 1);
  const min = 0;
  const range = max - min;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * (height - 4) - 2; // small inset
    return { x, y };
  });

  const linePath = points.reduce(
    (acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`,
    ""
  );

  const areaPath = `${linePath} L ${width.toFixed(1)} ${height} L 0 ${height} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={styles.svg}
      preserveAspectRatio="none"
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent-fade)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

