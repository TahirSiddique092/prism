import type { NextConfig } from "next";

// Statically exported. Served at the domain root (e.g. on Vercel), so no base
// path by default. Set BASE_PATH (e.g. "/prism") only if hosting under a
// sub-path such as a GitHub Pages project site.
const basePath = process.env.BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
