import type { NextRequest } from "next/server";
import { proxyManagerRequest } from "./manager-proxy";

export function GET(request: NextRequest) {
  const query = request.nextUrl.search;
  return proxyManagerRequest(request, `/api/incidents${query}`);
}

export function POST(request: NextRequest) {
  return proxyManagerRequest(request, "/api/incidents");
}
