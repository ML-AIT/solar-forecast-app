import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solar Forecast Dashboard",
  description: "Day-ahead 15-minute PV power forecasts for PEA solar plants",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
