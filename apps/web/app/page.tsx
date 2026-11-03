"use client";

// The overview dashboard runs in the browser (static export, data fetched client-side).
// `ssr: false` skips pre-rendering at build time, so "tomorrow" is computed on the
// user's machine at page load instead of being frozen at build time.
import dynamic from "next/dynamic";

const OverviewDashboard = dynamic(() => import("@/components/OverviewDashboard"), {
  ssr: false,
  loading: () => (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "24px 24px" }}>
      <p style={{ color: "var(--muted)" }}>Loading solar overview…</p>
    </div>
  ),
});

export default function Page() {
  return <OverviewDashboard />;
}
