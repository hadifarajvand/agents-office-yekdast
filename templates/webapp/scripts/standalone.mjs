// After `next build`: copy what the standalone server needs next to it (static assets,
// public files, SQL migrations), so `npm start` and the Docker image run the same bundle.
import { cpSync, existsSync } from "node:fs";

const out = ".next/standalone";
cpSync(".next/static", `${out}/.next/static`, { recursive: true });
if (existsSync("public")) cpSync("public", `${out}/public`, { recursive: true });
cpSync("drizzle", `${out}/drizzle`, { recursive: true });
