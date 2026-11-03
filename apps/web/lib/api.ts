// All calls to the FastAPI backend live in this file.
// Types mirror the API contract in apps/api — update both together.

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

// ---------- Types ----------

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type Plant = {
  id: string; // e.g. "S01"
  name: string; // e.g. "S01 Sa Kaeo"
  capacity_kw: number;
  lat: number | null;
  lon: number | null;
};

export type ForecastPoint = {
  timestamp: string; // ISO 8601 with offset, e.g. "2026-10-17T00:00:00+07:00"
  p10: number; // kW, 10th percentile
  p50: number; // kW, median forecast
  p90: number; // kW, 90th percentile
};

export type Forecast = {
  plant_id: string;
  date: string; // YYYY-MM-DD (local date in Asia/Bangkok)
  issued_at: string;
  model_version: string;
  unit: "kW";
  resolution_minutes: number; // 15
  timezone: string; // "Asia/Bangkok"
  points: ForecastPoint[]; // 96 points for a full day
};

export type Health = {
  status: string; // "ok" when healthy
  [key: string]: unknown;
};

// ---------- Helpers ----------

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    // FastAPI errors look like {"detail": "..."}; show that if present.
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // response was not JSON — keep statusText
    }
    throw new ApiError(res.status, `API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

// ---------- Endpoints ----------

export function getHealth(): Promise<Health> {
  return getJson<Health>("/health");
}

export function getPlants(): Promise<Plant[]> {
  return getJson<Plant[]>("/api/v1/plants");
}

export function getForecast(plantId: string, date: string): Promise<Forecast> {
  const query = new URLSearchParams({ plant_id: plantId, date });
  return getJson<Forecast>(`/api/v1/forecast?${query}`);
}
