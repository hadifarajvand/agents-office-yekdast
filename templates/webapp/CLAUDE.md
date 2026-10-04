# Building on this template

You are extending a working app, not starting one. It already builds, tests, starts and passes
its browser tests. Keep it that way: the platform runs `npm ci`, `npm run build`, `npm test`,
`npm start` + `GET /healthz`, and `npm run test:e2e` after you finish, and any red step sends
the work back to you with the output.

## Stack (do not swap pieces)
- Next.js App Router + TypeScript (`src/app`). Server components by default; `"use client"` only where needed.
- Database: Drizzle ORM (`src/db/schema.ts`). Empty `DATABASE_URL` = in-process PGlite (dev, tests);
  production sets `DATABASE_URL` to Postgres. After changing the schema run `npm run db:generate`
  and commit the new file in `drizzle/`. Never edit an existing migration.
- Auth: Better Auth, email + password (`src/lib/auth.ts`, `/sign-in`, `/admin` is signed-in only).
- Validation: zod at every server entry point (see `src/lib/items.ts`).
- Payments, if the brief asks for them: add `stripe`, read `STRIPE_SECRET_KEY` from the environment,
  use Checkout in test mode. Never hard-code a key.

## How to add a feature
1. Model it in `src/db/schema.ts`, run `npm run db:generate`.
2. Server functions in `src/lib/<thing>.ts` (validate input with zod, `await ready()` before queries).
3. Pages in `src/app/...`; forms post to server actions (`src/app/actions.ts` pattern).
4. A unit test per server function in `tests/` (Vitest, runs on PGlite) and a browser test per
   acceptance criterion in `e2e/` (Playwright; use labels and roles, not CSS classes).
5. Replace the example `items` resource when the product does not need it; keep `/healthz`.

## Rules
- `npm test` and `npm run test:e2e` must pass before you stop. Run them.
- No secrets, keys or real customer data in the code. Configuration comes from environment
  variables listed in `.env.example` (names only).
- Keep the Dockerfile, `scripts/standalone.mjs`, `/healthz` and the `start` script working.
- Update README.md: what the app does, how to run it, which environment variables it needs.
