import type { NextRequest } from "next/server";
import { proxyManagerRequest } from "../../manager-proxy";

interface IncidentStatusRouteContext {
  params: { id: string };
}

export function PATCH(request: NextRequest, { params }: IncidentStatusRouteContext) {
  return proxyManagerRequest(
    request,
    `/api/incidents/${encodeURIComponent(params.id)}/status`,
  );
}
