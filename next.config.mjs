/** @type {import('next').NextConfig} */
const apiInternalUrl = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiInternalUrl}/:path*`,
      },
      {
        source: "/api/suppliers/:path*",
        destination: `${apiInternalUrl}/suppliers/:path*`,
      },
      {
        source: "/api/incidents-service/:path*",
        destination: `${apiInternalUrl}/incidents/:path*`,
      },
      {
        source: "/api/telemetry/:path*",
        destination: `${apiInternalUrl}/telemetry/:path*`,
      },
    ];
  },
};

export default nextConfig;
