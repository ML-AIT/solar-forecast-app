import styles from "./OverviewKpis.module.css";

type OverviewKpisProps = {
  totalEnergyKwh: number;
  completePlantsCount: number;
  totalPlantsCount: number;
  latestIssuedAt: string | null;
  formattedEnergy: { value: string; unit: string };
  formattedIssueTime: string;
};

export default function OverviewKpis({
  completePlantsCount,
  totalPlantsCount,
  formattedEnergy,
  formattedIssueTime,
}: OverviewKpisProps) {
  return (
    <section className={styles.tiles} aria-label="System overview key performance indicators">
      <div className={styles.tile}>
        <span className={styles.tileLabel}>
          Total Energy (P50) · {completePlantsCount} of {totalPlantsCount} plants
        </span>
        <div className={styles.tileValue}>
          {completePlantsCount > 0 ? formattedEnergy.value : "–"}
          {completePlantsCount > 0 && <small className={styles.tileUnit}> {formattedEnergy.unit}</small>}
        </div>
      </div>

      <div className={styles.tile}>
        <span className={styles.tileLabel}>Plants with forecast</span>
        <div className={styles.tileValue}>
          {completePlantsCount} <small className={styles.tileUnit}>/ {totalPlantsCount}</small>
        </div>
      </div>

      <div className={styles.tile}>
        <span className={styles.tileLabel}>Latest issue</span>
        <div className={styles.tileValueSmall}>
          {formattedIssueTime || "–"}
        </div>
      </div>
    </section>
  );
}

