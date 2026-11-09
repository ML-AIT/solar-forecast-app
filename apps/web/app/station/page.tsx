"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";

const StationDashboard = dynamic(() => import("@/components/StationDashboard"), {
  ssr: false,
  loading: () => (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "24px" }}>
      <p style={{ color: "var(--muted)" }}>Loading station…</p>
    </div>
  ),
});

export default function StationPage() {
  return (
    <Suspense
      fallback={
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "24px" }}>
          <p style={{ color: "var(--muted)" }}>Loading station…</p>
        </div>
      }
    >
      <StationDashboard />
    </Suspense>
  );
}

