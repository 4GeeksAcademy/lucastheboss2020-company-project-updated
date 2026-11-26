import type { Metadata } from "next";
import WebsiteHome from "../../../uis/website/WebsiteHome";
import DesignFoundations from "../../../uis/website/DesignFoundations";
import BackofficeNavigationPreview from "../../../uis/backoffice/BackofficeNavigationPreview";

export const metadata: Metadata = {
  title: "TrackFlow Logistics",
  description: "Warehouse management, last-mile delivery, and reverse logistics for e-commerce in the United States and Spain.",
};

export default function WebsiteRoute({ searchParams }: { searchParams: { preview?: string } }) {
  if (searchParams.preview === "backoffice-navigation") return <BackofficeNavigationPreview />;
  return searchParams.preview === "foundations" ? <DesignFoundations /> : <WebsiteHome />;
}
