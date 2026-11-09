"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import {
  SLOTS_PER_DAY,
  daylight,
  daylightRange,
  fleetSeries,
  p50At,
  peakSlot,
  slotTime,
  twilight,
} from "@/lib/dayReplay";
import { formatNumber } from "@/lib/format";
import { MAP_HEIGHT, MAP_WIDTH, NEIGHBOURS_PATH, THAILAND_PATH, projectToMap } from "@/lib/thailandMap";
import StatusBadge, { STATUS_CONFIG } from "./StatusBadge";
import { getStationStatus, summarizeForecast, type PlantForecastState } from "./StationCard";
import styles from "./StationMap.module.css";

type StationMapProps = {
  states: PlantForecastState[];
  highlightedId: string | null;
  onHighlight: (plantId: string | null) => void;
};

// Reference point so the map is easy to read at a glance.
const BANGKOK = projectToMap(100.5018, 13.7563);

// Slots are forecast point indices: the API contract guarantees 96 points from 00:00.
// One 15-minute slot per step: sunrise to sunset plays in about 6 seconds.
const STEP_MS = 110;

// Largest station glow radius (map units), reached at full capacity.
const GLOW_RADIUS = 50;

function stationHref(plantId: string): string {
  return `/station/?id=${encodeURIComponent(plantId)}`;
}

/** kW as a short power string: "850 kW" or "4.2 MW". */
function formatPower(kw: number): string {
  return kw >= 1000 ? `${formatNumber(kw / 1000, 1)} MW` : `${formatNumber(kw)} kW`;
}

export default function StationMap({ states, highlightedId, onHighlight }: StationMapProps) {
  const placed = states.filter(
    (s): s is PlantForecastState & { plant: { lat: number; lon: number } } =>
      s.plant.lat !== null && s.plant.lon !== null,
  );
  const unplaced = states.filter((s) => s.plant.lat === null || s.plant.lon === null);
  const active = placed.find((s) => s.plant.id === highlightedId);

  // Day replay. Until someone scrubs or plays, the map shows the fleet's peak slot.
  const series = fleetSeries(states.map((s) => s.forecast));
  const range = daylightRange(series);
  const [chosenSlot, setChosenSlot] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const slot = chosenSlot ?? peakSlot(series);

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (slot >= range.end) setPlaying(false);
      else setChosenSlot(slot + 1);
    }, STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, slot, range.end]);

  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    // Start again from dawn unless paused partway through the day.
    if (chosenSlot === null || slot >= range.end || slot < range.start) setChosenSlot(range.start);
    setPlaying(true);
  };

  const fleetCapacity = states.reduce(
    (sum, s) => (s.forecast ? sum + s.plant.capacity_kw : sum),
    0,
  );
  const fleetNow = series[slot] ?? 0;
  const fleetShare = fleetCapacity > 0 ? fleetNow / fleetCapacity : 0;
  const sky = daylight(slot);
  const warm = twilight(slot);

  const gradientId = useId();

  return (
    <section className={styles.card} aria-labelledby="station-map-title">
      <div className={styles.head}>
        <h2 id="station-map-title" className={styles.title}>
          Station map
        </h2>
        <span className={styles.count}>
          {placed.length} of {states.length} located
        </span>
      </div>

      <div className={styles.mapWrap}>
        <svg
          className={styles.svg}
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          role="group"
          aria-label={`Map of Thailand with ${placed.length} solar stations at ${slotTime(slot)}. Select a station to open it.`}
        >
          <defs>
            <radialGradient id={gradientId}>
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.75" />
              <stop offset="45%" stopColor="var(--accent)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Sky: night base, then the day and twilight tints fade in with the chosen time. */}
          <g aria-hidden="true">
            <rect className={styles.skyNight} width={MAP_WIDTH} height={MAP_HEIGHT} />
            <rect className={styles.skyDay} width={MAP_WIDTH} height={MAP_HEIGHT} style={{ opacity: sky }} />
            <rect className={styles.skyDawn} width={MAP_WIDTH} height={MAP_HEIGHT} style={{ opacity: warm * 0.8 }} />
          </g>

          <path className={styles.neighbours} d={NEIGHBOURS_PATH} aria-hidden="true" />
          <path className={styles.country} d={THAILAND_PATH} aria-hidden="true" />
          <path
            className={styles.sunlight}
            d={THAILAND_PATH}
            style={{ opacity: sky * 0.08 + warm * 0.16 }}
            aria-hidden="true"
          />
          <rect
            className={styles.veil}
            width={MAP_WIDTH}
            height={MAP_HEIGHT}
            style={{ opacity: (1 - sky) * 0.35 }}
            aria-hidden="true"
          />

          <g aria-hidden="true">
            <rect className={styles.city} x={BANGKOK.x - 3} y={BANGKOK.y - 3} width={6} height={6} />
            <text className={styles.cityLabel} x={BANGKOK.x - 8} y={BANGKOK.y + 4} textAnchor="end">
              Bangkok
            </text>
          </g>

          {/* Power glow under the markers: area grows with P50 / capacity at the chosen time. */}
          <g aria-hidden="true">
            {placed.map(({ plant, forecast }) => {
              const kw = p50At(forecast, slot);
              if (kw === null || plant.capacity_kw <= 0) return null;
              const share = Math.max(0, Math.min(1, kw / plant.capacity_kw));
              const { x, y } = projectToMap(plant.lon, plant.lat);
              return (
                <circle
                  key={plant.id}
                  className={styles.glow}
                  cx={x}
                  cy={y}
                  r={GLOW_RADIUS}
                  fill={`url(#${gradientId})`}
                  style={{ transform: `scale(${Math.sqrt(share)})` }}
                />
              );
            })}
          </g>

          {placed.map((state) => {
            const { plant } = state;
            const { x, y } = projectToMap(plant.lon, plant.lat);
            const status = getStationStatus(state);
            const cfg = STATUS_CONFIG[status];
            const summary = summarizeForecast(state.forecast);
            const kw = p50At(state.forecast, slot);
            const isActive = plant.id === highlightedId;
            return (
              <a
                key={plant.id}
                href={stationHref(plant.id)}
                className={`${styles.marker} ${styles[cfg.variant]} ${isActive ? styles.active : ""}`}
                aria-label={`${plant.name}: ${cfg.label}. P50 energy ${summary.energy}. Peak ${summary.peak}.`}
                onMouseEnter={() => onHighlight(plant.id)}
                onMouseLeave={() => onHighlight(null)}
                onFocus={() => onHighlight(plant.id)}
                onBlur={() => onHighlight(null)}
              >
                <circle className={styles.hit} cx={x} cy={y} r={22} />
                <circle className={styles.halo} cx={x} cy={y} r={isActive ? 16 : 11} />
                <circle className={styles.dot} cx={x} cy={y} r={5} />
                <text className={styles.markerLabel} x={x + 12} y={y + 4}>
                  {plant.id} <tspan className={styles.markerSymbol}>{cfg.symbol}</tspan>
                  {kw !== null && (
                    <tspan className={styles.markerPower} x={x + 12} dy={16}>
                      {formatPower(kw)}
                    </tspan>
                  )}
                </text>
              </a>
            );
          })}
        </svg>

        <div className={styles.clock} aria-hidden="true">
          <span className={styles.clockTime}>{slotTime(slot)}</span>
          <span className={styles.clockLabel}>{chosenSlot === null ? "Fleet peak" : "Forecast time"}</span>
        </div>

        {active && (
          <MapTooltip
            state={active}
            x={projectToMap(active.plant.lon, active.plant.lat)}
            slot={slot}
          />
        )}
      </div>

      <DayTimeline
        series={series}
        slot={slot}
        playing={playing}
        fleetNow={fleetNow}
        fleetShare={fleetShare}
        onTogglePlay={togglePlay}
        onScrub={(i) => {
          setPlaying(false);
          setChosenSlot(i);
        }}
      />

      <ul className={styles.legend} aria-label="Marker legend">
        <li className={styles.ok}>● Ready</li>
        <li className={styles.warn}>⚠ Stale / fallback</li>
        <li className={styles.bad}>✖ No forecast / error</li>
        <li className={styles.glowKey}>◉ Glow = P50 vs capacity</li>
      </ul>

      {unplaced.length > 0 && (
        <div className={styles.unplaced}>
          <h3 className={styles.unplacedTitle}>Location not confirmed</h3>
          <ul className={styles.unplacedList}>
            {unplaced.map((state) => (
              <li key={state.plant.id}>
                <Link
                  href={stationHref(state.plant.id)}
                  className={`${styles.unplacedLink} ${
                    state.plant.id === highlightedId ? styles.unplacedActive : ""
                  }`}
                  onMouseEnter={() => onHighlight(state.plant.id)}
                  onMouseLeave={() => onHighlight(null)}
                  onFocus={() => onHighlight(state.plant.id)}
                  onBlur={() => onHighlight(null)}
                >
                  <span className={styles.unplacedName}>{state.plant.name}</span>
                  <StatusBadge status={getStationStatus(state)} mode={state.forecast?.forecast_mode} />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

type DayTimelineProps = {
  series: number[];
  slot: number;
  playing: boolean;
  fleetNow: number;
  fleetShare: number;
  onTogglePlay: () => void;
  onScrub: (slot: number) => void;
};

/** Fleet P50 through the day, with a play button and a slider to pick the time shown on the map. */
function DayTimeline({
  series,
  slot,
  playing,
  fleetNow,
  fleetShare,
  onTogglePlay,
  onScrub,
}: DayTimelineProps) {
  const max = Math.max(...series, 1);
  const height = 40;
  const points = series.map((v, i) => `${i + 0.5},${height - (v / max) * (height - 4)}`);
  const area = `M0.5,${height} L${points.join(" L")} L${SLOTS_PER_DAY - 0.5},${height} Z`;
  const line = `M${points.join(" L")}`;
  const sliderId = useId();

  return (
    <div className={styles.timeline}>
      <div className={styles.timelineHead}>
        <button
          type="button"
          className={styles.playButton}
          onClick={onTogglePlay}
          aria-label={playing ? "Pause" : "Play the day: tomorrow's forecast"}
        >
          {playing ? (
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <rect x="3" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
              <rect x="9.5" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M4 2.5v11a.5.5 0 0 0 .77.42l8.5-5.5a.5.5 0 0 0 0-.84l-8.5-5.5A.5.5 0 0 0 4 2.5Z" fill="currentColor" />
            </svg>
          )}
          <span>{playing ? "Pause" : "Play the day"}</span>
        </button>

        <div className={styles.fleetNow}>
          <span className={styles.fleetValue}>{formatPower(fleetNow)}</span>
          <span className={styles.fleetLabel}>
            Fleet P50 at {slotTime(slot)} · {formatNumber(fleetShare * 100)}% of capacity
          </span>
        </div>
      </div>

      <div className={styles.curveWrap}>
        <svg
          className={styles.curve}
          viewBox={`0 0 ${SLOTS_PER_DAY} ${height}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d={area} className={styles.curveArea} />
          <path d={line} className={styles.curveLine} vectorEffect="non-scaling-stroke" />
          <line
            className={styles.cursor}
            x1={slot + 0.5}
            x2={slot + 0.5}
            y1={0}
            y2={height}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <label htmlFor={sliderId} className="sr-only">
          Forecast time shown on the map
        </label>
        <input
          id={sliderId}
          type="range"
          className={styles.slider}
          min={0}
          max={SLOTS_PER_DAY - 1}
          step={1}
          value={slot}
          onChange={(e) => onScrub(Number(e.target.value))}
          aria-valuetext={`${slotTime(slot)}, fleet P50 ${formatPower(fleetNow)}`}
        />
      </div>
      <div className={styles.ticks} aria-hidden="true">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
    </div>
  );
}

function MapTooltip({
  state,
  x,
  slot,
}: {
  state: PlantForecastState;
  x: { x: number; y: number };
  slot: number;
}) {
  const summary = summarizeForecast(state.forecast);
  const kw = p50At(state.forecast, slot);
  const leftPct = (x.x / MAP_WIDTH) * 100;
  const topPct = (x.y / MAP_HEIGHT) * 100;
  // Keep the tooltip inside the card: anchor it to the side away from the nearest edge.
  const alignRight = leftPct > 55;

  return (
    <div
      className={`${styles.tooltip} ${alignRight ? styles.tooltipRight : ""}`}
      style={{ left: `${leftPct}%`, top: `${topPct}%` }}
      aria-hidden="true"
    >
      <div className={styles.tooltipHead}>
        <span className={styles.tooltipName}>{state.plant.name}</span>
        <StatusBadge status={getStationStatus(state)} mode={state.forecast?.forecast_mode} />
      </div>
      <dl className={styles.tooltipStats}>
        {kw !== null && (
          <div>
            <dt>P50 at {slotTime(slot)}</dt>
            <dd>{formatPower(kw)}</dd>
          </div>
        )}
        <div>
          <dt>P50 energy</dt>
          <dd>{summary.energy}</dd>
        </div>
        <div>
          <dt>Peak</dt>
          <dd>{summary.peak}</dd>
        </div>
        <div>
          <dt>Capacity</dt>
          <dd>{formatNumber(state.plant.capacity_kw)} kW</dd>
        </div>
      </dl>
      <span className={styles.tooltipHint}>Click to open station</span>
    </div>
  );
}
