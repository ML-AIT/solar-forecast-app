import type { Forecast } from "@/lib/api";
import { formatEnergy, formatNumber, toHHMM } from "@/lib/format";
import styles from "./StationKpis.module.css";

type StationKpisProps = {
  forecast?: Forecast | null;
  capacityKw: number;
};

export default function StationKpis({ forecast, capacityKw }: StationKpisProps) {
  let energyStr = "–";
  let energyUnit = "";
  let peakStr = "–";
  let peakTimeStr: string | null = null;
  let ratioStr = "–";

  if (forecast && forecast.points.length > 0) {
    const hours = (forecast.resolution_minutes ?? 15) / 60;
    const totalKwh = forecast.points.reduce((sum, p) => sum + p.p50, 0) * hours;
    const formattedEnergy = formatEnergy(totalKwh);
    energyStr = formattedEnergy.value;
    energyUnit = formattedEnergy.unit;

    let peakPoint = forecast.points[0];
    for (const pt of forecast.points) {
      if (pt.p50 > peakPoint.p50) {
        peakPoint = pt;
      }
    }

    peakStr = formatNumber(peakPoint.p50);
    peakTimeStr = `at ${toHHMM(peakPoint.timestamp)}`;

    if (capacityKw > 0) {
      const ratio = (peakPoint.p50 / capacityKw) * 100;
      ratioStr = ratio.toFixed(1);
    }
  }

  return (
    <section className={styles.tiles} aria-label="Station forecast key performance indicators">
      <div className={styles.tile}>
        <span className={styles.tileLabel}>Forecast Energy (P50)</span>
        <div className={styles.tileValue}>
          <span>{energyStr}</span>
          {energyUnit && <small className={styles.tileUnit}>{energyUnit}</small>}
        </div>
      </div>

      <div className={styles.tile}>
        <span className={styles.tileLabel}>Peak Power (P50)</span>
        <div className={styles.tileValue}>
          <span>{peakStr}</span>
          {peakStr !== "–" && <small className={styles.tileUnit}>kW</small>}
          {peakTimeStr && <span className={styles.tileDetail}>{peakTimeStr}</span>}
        </div>
      </div>

      <div className={styles.tile}>
        <span className={styles.tileLabel}>Peak / Capacity</span>
        <div className={styles.tileValue}>
          <span>{ratioStr}</span>
          {ratioStr !== "–" && <small className={styles.tileUnit}>%</small>}
        </div>
      </div>
    </section>
  );
}

