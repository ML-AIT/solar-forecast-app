import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build a fully static site into `out/` (deployed to Azure Static Web Apps).
  // This means: no API routes, no server-side data fetching at request time.
  output: "export",
  // The Next.js image optimizer needs a server, so turn it off for static export.
  images: { unoptimized: true },
  // `/about` -> `/about/index.html`, which static hosts serve without rewrites.
  trailingSlash: true,
  // apps/web has its own package-lock.json; tell Turbopack this folder is the root.
  turbopack: { root: __dirname },
};

export default nextConfig;
