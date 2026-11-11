import type { Metadata } from "next";
import "./globals.css";
import Navigation from "./Navigation";
import { AuthProvider } from "./auth/AuthProvider";
import TelemetryProvider from "./telemetry/TelemetryProvider";

export const metadata: Metadata = {
  title: "TrackFlow Lead Candidates",
  description: "TrackFlow lead-candidate pipeline for e-commerce logistics opportunities.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TelemetryProvider>
          <AuthProvider>
            <Navigation />
            <main className="shell">{children}</main>
          </AuthProvider>
        </TelemetryProvider>
      </body>
    </html>
  );
}
