import Link from "next/link";
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

function stationHref(plantId: string): string {
  return `/station/?id=${encodeURIComponent(plantId)}`;
}

export default function StationMap({ states, highlightedId, onHighlight }: StationMapProps) {
  const placed = states.filter(
    (s): s is PlantForecastState & { plant: { lat: number; lon: number } } =>
      s.plant.lat !== null && s.plant.lon !== null,
  );
  const unplaced = states.filter((s) => s.plant.lat === null || s.plant.lon === null);
  const active = placed.find((s) => s.plant.id === highlightedId);

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
          aria-label={`Map of Thailand with ${placed.length} solar stations. Select a station to open it.`}
        >
          <path className={styles.neighbours} d={NEIGHBOURS_PATH} aria-hidden="true" />
          <path className={styles.country} d={THAILAND_PATH} aria-hidden="true" />

          <g aria-hidden="true">
            <rect className={styles.city} x={BANGKOK.x - 3} y={BANGKOK.y - 3} width={6} height={6} />
            <text className={styles.cityLabel} x={BANGKOK.x - 8} y={BANGKOK.y + 4} textAnchor="end">
              Bangkok
            </text>
          </g>

          {placed.map((state) => {
            const { plant } = state;
            const { x, y } = projectToMap(plant.lon, plant.lat);
            const status = getStationStatus(state);
            const cfg = STATUS_CONFIG[status];
            const summary = summarizeForecast(state.forecast);
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
                </text>
              </a>
            );
          })}
        </svg>

        {active && (
          <MapTooltip state={active} x={projectToMap(active.plant.lon, active.plant.lat)} />
        )}
      </div>

      <ul className={styles.legend} aria-label="Marker legend">
        <li className={styles.ok}>● Ready</li>
        <li className={styles.warn}>⚠ Stale / fallback</li>
        <li className={styles.bad}>✖ No forecast / error</li>
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

function MapTooltip({ state, x }: { state: PlantForecastState; x: { x: number; y: number } }) {
  const summary = summarizeForecast(state.forecast);
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
