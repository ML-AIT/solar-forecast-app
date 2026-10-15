import { formatNumber } from "@/lib/format";
import styles from "./Dashboard.module.css";

type Props = {
  label: string;
  value: number | null; // null → show "–" (not loaded yet)
  unit: string;
};

export default function StatTile({ label, value, unit }: Props) {
  return (
    <div className={styles.tile}>
      <div className={styles.tileLabel}>{label}</div>
      <div className={styles.tileValue}>
        {value === null ? "–" : formatNumber(value)}
        <span className={styles.tileUnit}> {unit}</span>
      </div>
    </div>
  );
}
