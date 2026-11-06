import path from "node:path";

import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Single source of configuration: the repo-root .env (shared with the API and scripts).
loadEnvConfig(path.resolve(process.cwd(), "../.."));

// Rewrites are resolved when the server starts / at build: set API_INTERNAL_URL before `next build`.
const apiUrl = (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Same-origin API proxy (TRD §5): the browser never talks to FastAPI directly, so no CORS.
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiUrl}/api/v1/:path*` },
      { source: "/api/docs", destination: `${apiUrl}/api/docs` },
      { source: "/api/openapi.json", destination: `${apiUrl}/api/openapi.json` },
    ];
  },
};

export default nextConfig;
