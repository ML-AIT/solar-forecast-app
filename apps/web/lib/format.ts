// Small date / number helpers. All plant times are Asia/Bangkok (UTC+7).

export const PLANT_TIMEZONE = "Asia/Bangkok";

/** Tomorrow's date in Bangkok as "YYYY-MM-DD" (the day-ahead forecast target). */
export function tomorrowInBangkok(): string {
  // "en-CA" formats dates as YYYY-MM-DD.
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: PLANT_TIMEZONE,
  }).format(new Date());
  const d = new Date(`${today}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** "2026-10-17T13:45:00+07:00" -> "13:45" (uses the local time written in the string). */
export function toHHMM(timestamp: string): string {
  return timestamp.slice(11, 16);
}

/** Format an ISO timestamp in Bangkok time, e.g. "16 Oct 2026, 23:55". */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: PLANT_TIMEZONE,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

/** 12345.6 -> "12,346" */
export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * Format energy according to G4:
 * Shows energy above 10,000 kWh as MWh with one decimal (e.g. 12,500 kWh -> "12.5", unit: "MWh").
 * Otherwise shows kWh formatted as whole integer (e.g. 4,812 kWh -> "4,812", unit: "kWh").
 */
export function formatEnergy(kwh: number): { value: string; unit: string } {
  if (kwh >= 10_000) {
    const mwh = kwh / 1000;
    return {
      value: formatNumber(mwh, 1),
      unit: "MWh",
    };
  }
  return {
    value: formatNumber(Math.round(kwh)),
    unit: "kWh",
  };
}

/**
 * Compute the age of a forecast relative to "now".
 * Rule S5/O3: If issued_at is in the future, return null (display issue time without age).
 * Never show a negative age.
 * E.g. "2 h ago", "45 min ago", "1 d ago".
 */
export function formatForecastAge(issuedAtIso: string, now: Date = new Date()): string | null {
  const issued = new Date(issuedAtIso);
  if (Number.isNaN(issued.getTime())) return null;

  const diffMs = now.getTime() - issued.getTime();
  if (diffMs <= 0) {
    // In future or right now
    return null;
  }

  const diffMinutes = Math.floor(diffMs / 60_000);
  if (diffMinutes < 60) {
    return `${Math.max(1, diffMinutes)} min ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} d ago`;
}

/** Check if a forecast was issued more than 36 hours ago. */
export function isForecastStale(issuedAtIso: string, now: Date = new Date()): boolean {
  const issued = new Date(issuedAtIso);
  if (Number.isNaN(issued.getTime())) return false;
  const diffHours = (now.getTime() - issued.getTime()) / (1000 * 60 * 60);
  return diffHours > 36;
}

