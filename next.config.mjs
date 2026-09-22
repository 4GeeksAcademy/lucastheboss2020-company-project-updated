/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/suppliers/:path*",
        destination: "http://localhost:8001/suppliers/:path*",
      },
    ];
  },
};

export default nextConfig;
