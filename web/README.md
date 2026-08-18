# IELTS Learning Agent Web

Chinese-first Phase 5 web MVP built with Next.js, TypeScript, and Tailwind.

## Commands

- `npm run dev` — start the frontend (set `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`)
- `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
- `npm run test:e2e` — real Chromium E2E; requires Python dependencies and `IELTS_E2E_DATABASE_URL` pointing to isolated PostgreSQL.

The frontend is presentation only. FastAPI owns evaluation, learner state, planning and practice lifecycle; PostgreSQL is the source of truth. Browser storage is restricted to learner navigation and recommendation presentation data, never essays, evaluations, provider payloads, or secrets.