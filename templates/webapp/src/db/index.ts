import path from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { drizzle as drizzleLite } from "drizzle-orm/pglite";
import { migrate as migrateLite } from "drizzle-orm/pglite/migrator";
import { drizzle as drizzlePg } from "drizzle-orm/node-postgres";
import { migrate as migratePg } from "drizzle-orm/node-postgres/migrator";
import { Pool } from "pg";
import * as schema from "./schema";

// DATABASE_URL set   -> Postgres (production, previews with a database).
// DATABASE_URL empty -> PGlite, Postgres compiled to WASM, in-process: dev, tests and the
//                       container checks need no database server. PGLITE_DIR keeps it on disk.
const url = process.env.DATABASE_URL;
const migrationsFolder = process.env.MIGRATIONS_DIR || path.join(process.cwd(), "drizzle");

function open() {
  if (url) {
    const db = drizzlePg(new Pool({ connectionString: url, max: 10 }), { schema });
    return { db, migrate: () => migratePg(db, { migrationsFolder }) };
  }
  const db = drizzleLite(new PGlite(process.env.PGLITE_DIR || undefined), { schema });
  return { db, migrate: () => migrateLite(db, { migrationsFolder }) };
}

const g = globalThis as unknown as { __db?: ReturnType<typeof open>; __ready?: Promise<void> };
const conn = (g.__db ??= open());

export const db = conn.db;

/** Applies the SQL migrations in ./drizzle once per process. Await it before the first query. */
export function ready(): Promise<void> {
  return (g.__ready ??= conn.migrate().then(() => undefined));
}
