import type { NextConfig } from "next";

// Served from https://<org>.github.io/<repo>/ via GitHub Pages (see
// .github/workflows/pages.yml), so assets need the repo name as a base
// path — but only in that CI build, not for local `next dev`/`next build`.
// GITHUB_REPOSITORY (e.g. "YourAmaryllis/lit") is set automatically by
// GitHub Actions; this stays blank for local runs.
const repo = process.env.GITHUB_REPOSITORY?.split("/")[1];
const basePath = repo ? `/${repo}` : "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath ? `${basePath}/` : undefined,
};

export default nextConfig;
