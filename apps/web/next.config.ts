import type { NextConfig } from "next";

/**
 * EntityGraph Auditor web UI.
 *
 * This front end is a client-rendered SPA shell that talks to the FastAPI
 * backend at NEXT_PUBLIC_API_BASE. We intentionally keep `cacheComponents`
 * disabled: every data view is fetched on the client with TanStack Query, so the
 * Cache Components / PPR model (which expects cached server data behind
 * <Suspense>) would add blocking-build constraints without any benefit here.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
