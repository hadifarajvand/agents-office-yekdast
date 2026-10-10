// After `next build`: copy what the standalone server needs next to it (static assets,
// public files, SQL migrations), so `npm start` and the Docker image run the same bundle.
//
// A plain walk instead of fs.cpSync(..., { recursive: true }): the native recursive copy fails
// with EACCES on a bind-mounted workspace (the job container on macOS/virtiofs) while copying
// into a directory it has just created.
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

function copyTree(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const name of readdirSync(src)) {
    const from = join(src, name);
    const to = join(dest, name);
    if (statSync(from).isDirectory()) copyTree(from, to);
    else copyFileSync(from, to);
  }
}

const out = ".next/standalone";
copyTree(".next/static", `${out}/.next/static`);
if (existsSync("public")) copyTree("public", `${out}/public`);
copyTree("drizzle", `${out}/drizzle`);
