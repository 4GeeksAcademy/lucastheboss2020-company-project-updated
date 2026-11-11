import type { NextRequest } from "next/server";
import { proxyManagerRequest } from "../manager-proxy";

interface IncidentRouteContext {
  params: { id: string };
}

export function GET(request: NextRequest, { params }: IncidentRouteContext) {
  return proxyManagerRequest(request, `/api/incidents/${encodeURIComponent(params.id)}`);
}
