import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Verification builds can use an isolated output without replacing the
  // bundle currently served by the LAN production process.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
