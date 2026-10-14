import type { NextConfig } from "next";

// Served from GitHub Pages at https://<user>.github.io/prism/, so the app is
// statically exported under the "/prism" base path. Override via BASE_PATH
// (e.g. "" for a custom domain or local preview at the root).
const basePath = process.env.BASE_PATH ?? "/prism";

const nextConfig: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
