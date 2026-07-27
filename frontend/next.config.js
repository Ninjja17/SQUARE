/** @type {import('next').NextConfig} */
const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || "https://square-production-a6f7.up.railway.app").trim();
const apiUrl = rawApiUrl.startsWith("http://") || rawApiUrl.startsWith("https://")
  ? rawApiUrl
  : `https://${rawApiUrl}`;

const cleanApiUrl = apiUrl.replace(/\/$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${cleanApiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

