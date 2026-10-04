import { randomBytes } from "node:crypto";
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { nextCookies } from "better-auth/next-js";
import { db } from "@/db";
import * as schema from "@/db/schema";

function secret(): string {
  if (process.env.BETTER_AUTH_SECRET) return process.env.BETTER_AUTH_SECRET;
  // No secret configured (dev, tests, preview checks): a random one per process. Sessions do not
  // survive a restart, which is safe; production sets BETTER_AUTH_SECRET (promote checklist).
  // Stored in process.env so every server bundle in this process signs with the same one.
  if (process.env.NODE_ENV === "production") console.warn("BETTER_AUTH_SECRET is not set: sessions end on restart");
  process.env.BETTER_AUTH_SECRET = randomBytes(32).toString("hex");
  return process.env.BETTER_AUTH_SECRET;
}

// The public URL. Deployments set BETTER_AUTH_URL; otherwise it is the address this server
// listens on (dev, tests and the container checks), so sign-in works without configuration.
const baseURL = process.env.BETTER_AUTH_URL || `http://${process.env.HOSTNAME || "localhost"}:${process.env.PORT || 3000}`;

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "pg", schema }),
  emailAndPassword: { enabled: true },
  secret: secret(),
  baseURL,
  trustedOrigins: [baseURL],
  plugins: [nextCookies()],
});
