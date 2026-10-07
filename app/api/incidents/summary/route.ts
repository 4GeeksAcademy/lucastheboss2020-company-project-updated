import type { NextRequest } from "next/server";
import { proxyManagerRequest } from "../manager-proxy";

export function GET(request: NextRequest) {
  return proxyManagerRequest(request, "/api/incidents/summary");
}
