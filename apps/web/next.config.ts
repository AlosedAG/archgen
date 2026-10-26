import path from "node:path";

import type { NextConfig } from "next";

// The API (apps/api). The browser only ever talks to this app; /api/* is
// proxied so the session cookie stays first-party and no CORS is needed.
// In production it comes from .env.production at build time (see the
// deployment guide); locally it defaults to the API on port 8000.
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Browser security headers on every page: no framing by other sites
// (clickjacking), no MIME sniffing, no full URLs leaked to other sites, and
// a content policy limiting where scripts, styles and data may come from.
// Next.js needs inline scripts/styles for hydration; everything else is same-origin.
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // `next dev` evaluates code for hot reload; production builds never do.
      process.env.NODE_ENV === "production"
        ? "script-src 'self' 'unsafe-inline'"
        : "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `next dev`'s badge defaults to bottom-left, on top of the rail's Help icon.
  devIndicators: { position: "bottom-right" },
  // A self-contained server bundle (.next/standalone) for the container image.
  output: "standalone",
  poweredByHeader: false,
  // Resolve from this app, not a lockfile that happens to sit higher up the disk.
  turbopack: { root: path.join(__dirname) },
  experimental: {
    // Uploads pass through the /api proxy, which cuts bodies off at 10 MB by
    // default; the API accepts library files up to 25 MB.
    proxyClientMaxBodySize: "26mb",
    // ...and gives up on a request that has been silent for 30 s by default.
    // A large portal read or an AI draft waiting for its first words can take
    // longer; match the API's 5-minute request limit on Cloud Run.
    proxyTimeout: 300_000,
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      // One small health check for both services: hitting it wakes this app
      // and, through it, the API (what the keep-alive job pings).
      { source: "/healthz", destination: `${API_URL}/healthz` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
