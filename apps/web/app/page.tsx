"use client";

// The whole dashboard runs in the browser (static export, data fetched client-side).
// `ssr: false` skips pre-rendering at build time, so "tomorrow" is computed on the
// user's machine at page load instead of being frozen at build time.
import dynamic from "next/dynamic";

const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  ssr: false,
  loading: () => <p style={{ padding: 24 }}>Loading dashboard…</p>,
});

export default function Page() {
  return <Dashboard />;
}
