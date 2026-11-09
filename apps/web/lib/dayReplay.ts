// Helpers for the station map's day replay: which 15-minute slot is shown and how bright it is.

import { type Forecast } from "./api";

export const SLOTS_PER_DAY = 96;
const SLOT_HOURS = 0.25;

/** "HH:MM" for slot i (interval-start labelled, like the forecast points). */
export function slotTime(i: number): string {
  const minutes = i * 15;
  const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
  const mm = String(minutes % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

/** P50 at slot i in kW, or null when the forecast does not cover that slot. */
export function p50At(forecast: Forecast | undefined, i: number): number | null {
  const point = forecast?.points[i];
  return point ? point.p50 : null;
}

/** Fleet P50 (kW) per slot, summed over every plant that has a forecast. */
export function fleetSeries(forecasts: (Forecast | undefined)[]): number[] {
  const series = new Array<number>(SLOTS_PER_DAY).fill(0);
  for (const forecast of forecasts) {
    if (!forecast) continue;
    forecast.points.slice(0, SLOTS_PER_DAY).forEach((p, i) => {
      series[i] += p.p50;
    });
  }
  return series;
}

/** Slots the replay plays through: from just before the first power to just after the last. */
export function daylightRange(series: number[]): { start: number; end: number } {
  const first = series.findIndex((v) => v > 0);
  if (first === -1) return { start: 24, end: 76 }; // 06:00–19:00 when there is no forecast
  let last = first;
  series.forEach((v, i) => {
    if (v > 0) last = i;
  });
  return { start: Math.max(0, first - 2), end: Math.min(SLOTS_PER_DAY - 1, last + 2) };
}

/** Slot with the highest fleet P50 (midday when there is no forecast). */
export function peakSlot(series: number[]): number {
  let best = 48;
  let bestValue = 0;
  series.forEach((v, i) => {
    if (v > bestValue) {
      best = i;
      bestValue = v;
    }
  });
  return best;
}

/**
 * How bright the sky is at slot i, 0 (night) to 1 (noon). A rough Thai day, sunrise about 06:00 and
 * sunset about 18:30. It only tints the map; the station glow comes from the forecast itself.
 */
export function daylight(i: number): number {
  const hour = (i + 0.5) * SLOT_HOURS;
  const value = Math.sin((Math.PI * (hour - 6)) / 12.5);
  return Math.max(0, Math.min(1, value));
}

/** Warm tint near sunrise and sunset, 0 to 1. */
export function twilight(i: number): number {
  const d = daylight(i);
  if (d <= 0) {
    const hour = (i + 0.5) * SLOT_HOURS;
    // Fade in during the half hour before sunrise and out during the half hour after sunset.
    const fromEdge = Math.min(Math.abs(hour - 6), Math.abs(hour - 18.5));
    return Math.max(0, 1 - fromEdge / 0.5) * 0.6;
  }
  return Math.max(0, 1 - d / 0.45);
}
