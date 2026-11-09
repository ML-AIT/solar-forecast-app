import type { Forecast } from "./api";

/**
 * Trigger a browser download of a file generated in-memory.
 */
export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export forecast points to CSV format (S6):
 * timestamp,p10_kw,p50_kw,p90_kw
 */
export function exportForecastToCsv(forecast: Forecast) {
  const header = "timestamp,p10_kw,p50_kw,p90_kw";
  const rows = forecast.points.map(
    (p) => `${p.timestamp},${p.p10},${p.p50},${p.p90}`
  );
  const csvContent = [header, ...rows].join("\r\n");
  const filename = `forecast_${forecast.plant_id}_${forecast.date}.csv`;
  downloadFile(csvContent, filename, "text/csv;charset=utf-8;");
}

/**
 * Export raw forecast JSON (S6):
 * The API response as-is.
 */
export function exportForecastToJson(forecast: Forecast) {
  const jsonContent = JSON.stringify(forecast, null, 2);
  const filename = `forecast_${forecast.plant_id}_${forecast.date}.json`;
  downloadFile(jsonContent, filename, "application/json;charset=utf-8;");
}

