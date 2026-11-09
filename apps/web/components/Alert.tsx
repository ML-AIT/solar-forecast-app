import React from "react";
import styles from "./Alert.module.css";

type AlertVariant = "error" | "warn";

type AlertProps = {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  icon?: string;
};

export default function Alert({
  variant = "error",
  title,
  children,
  icon,
}: AlertProps) {
  const isWarn = variant === "warn";
  const defaultIcon = isWarn ? "⚠" : "✖";

  return (
    <div
      className={`${styles.alert} ${isWarn ? styles.warn : styles.bad}`}
      role="alert"
    >
      <span className={styles.icon} aria-hidden="true">
        {icon ?? defaultIcon}
      </span>
      <div className={styles.content}>
        {title && <div className={styles.title}>{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}

