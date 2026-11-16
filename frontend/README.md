# EquipTrack frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui (Radix), TanStack Query, next-themes.

## Run locally

```bash
cp .env.example .env.local      # API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:3000 (start the API first: docker compose up)
```

## How it talks to the API

- The browser only calls this Next.js app. `/api/backend/api/v1/...` is forwarded to FastAPI by
  `src/app/api/backend/[...path]/route.ts`, which attaches the JWT from an **httpOnly cookie**
  (page JavaScript can never read the token) and can only reach `API_URL` under `/api/v1/`.
- `/api/auth/login` and `/api/auth/logout` set and clear that cookie. `src/proxy.ts` sends visitors
  without a session to `/login`; the API still authorizes every request.
- Types come from the API contract: `python ../scripts/export_openapi.py && npm run gen:api` regenerates
  `src/lib/api/schema.d.ts`. CI fails if the committed contract and the API disagree.

## Scripts

`npm run dev` · `npm run build` · `npm run lint` · `npm run typecheck` · `npm run gen:api`
