/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/suppliers/:path*",
        destination: "http://localhost:8001/suppliers/:path*",
      },
      {
        source: "/api/incidents-service/:path*",
        destination: "http://localhost:8002/incidents/:path*",
      },
    ];
  },
};

export default nextConfig;
