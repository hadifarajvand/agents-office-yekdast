import type { NextConfig } from "next";

// "standalone" makes `npm start` and the Dockerfile run the same small server bundle.
const config: NextConfig = {
  output: "standalone",
  serverExternalPackages: ["@electric-sql/pglite"],
  poweredByHeader: false,
};

export default config;
