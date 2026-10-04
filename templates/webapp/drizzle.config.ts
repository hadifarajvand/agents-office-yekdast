import { defineConfig } from "drizzle-kit";

// `npm run db:generate` writes SQL migrations to ./drizzle from src/db/schema.ts.
// The app applies them itself at startup (src/db/index.ts), for PGlite and Postgres alike.
export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema.ts",
  out: "./drizzle",
});
