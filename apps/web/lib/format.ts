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
