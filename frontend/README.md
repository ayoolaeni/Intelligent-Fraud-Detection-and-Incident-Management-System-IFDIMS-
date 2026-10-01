# frontend

React 18 + TypeScript + Vite dashboard implementing Section 12 of the build
specification.

## Setup

```bash
npm install
npm run dev       # http://localhost:5173, proxies /api to http://localhost:8000
```

## Structure

- `src/api/` — typed Axios client (`client.ts`), response/request types
  (`types.ts`), one function per backend endpoint (`endpoints.ts`), and an
  authenticated-download helper (`download.ts`) for CSV/PDF reports and
  case attachments, since those need the `Authorization` header a plain
  `<a href>` can't send.
- `src/auth/` — `AuthContext` (login/logout, token in `sessionStorage`,
  redirect-to-login on 401) and `ProtectedRoute` (role guard).
- `src/components/` — layout (sidebar/topbar/notifications), badges, the
  SHAP explanation chart, table/pagination/modal helpers, formatters.
- `src/pages/` — one file per route (Section 12.1).

## Tests

```bash
npm test          # vitest run
npx tsc --noEmit  # type-check
```
