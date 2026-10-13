import path from "node:path";

import type { NextConfig } from "next";

// The API (apps/api). The browser only ever talks to this app; /api/* is
// proxied so the session cookie stays first-party and no CORS is needed.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Resolve from this app, not a lockfile that happens to sit higher up the disk.
  turbopack: { root: path.join(__dirname) },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
