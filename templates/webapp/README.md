# App

Built from the workshop web-app template (Next.js, Drizzle, Better Auth).

```bash
npm ci
npm run dev          # http://localhost:3000, in-process database
npm test             # unit tests (PGlite)
npm run build && npm run test:e2e   # browser tests against the production build
docker build -t app . && docker run -p 3000:3000 -e DATABASE_URL=... -e BETTER_AUTH_SECRET=... -e BETTER_AUTH_URL=... app
```

Environment variables: see `.env.example`.
