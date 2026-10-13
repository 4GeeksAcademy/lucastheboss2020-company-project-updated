import type { Metadata } from "next";
import "../../../app/globals.css";

export const metadata: Metadata = {
  title: "TrackFlow Logistics",
  description: "Warehouse management, last-mile delivery, and reverse logistics for e-commerce in the United States and Spain.",
};

export default function WebsiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}