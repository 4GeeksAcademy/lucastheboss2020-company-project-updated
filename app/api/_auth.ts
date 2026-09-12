import { createHmac, timingSafeEqual } from "node:crypto";

interface JwtPayload {
  user_uuid?: unknown;
  exp?: unknown;
}

function base64Url(value: string): Buffer {
  return Buffer.from(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4), "base64");
}

export function hasValidBearerToken(request: Request): boolean {
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer ")) return false;

  const token = authorization.slice("Bearer ".length).trim();
  const parts = token.split(".");
  if (parts.length !== 3) return false;

  const secret = process.env.JWT_SECRET_KEY;
  if (!secret) return false;

  try {
    const [encodedHeader, encodedPayload, encodedSignature] = parts;
    const header = JSON.parse(base64Url(encodedHeader).toString("utf8")) as { alg?: string; typ?: string };
    const payload = JSON.parse(base64Url(encodedPayload).toString("utf8")) as JwtPayload;
    if (header.alg !== "HS256" || header.typ !== "JWT" || typeof payload.user_uuid !== "string") return false;
    if (typeof payload.exp !== "number" || payload.exp <= Math.floor(Date.now() / 1000)) return false;

    const expected = createHmac("sha256", secret).update(`${encodedHeader}.${encodedPayload}`).digest();
    const received = base64Url(encodedSignature);
    return received.length === expected.length && timingSafeEqual(received, expected);
  } catch {
    return false;
  }
}

export function unauthorized(): Response {
  return Response.json({ error: "Authentication required." }, { status: 401, headers: { "WWW-Authenticate": "Bearer" } });
}

export function requireAuthentication(request: Request): Response | null {
  return hasValidBearerToken(request) ? null : unauthorized();
}
