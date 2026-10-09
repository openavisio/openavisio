# ADR 007: Server actions for authenticated mutations from client components

**Status:** Accepted

## Context

Several UI features (password change, profile update, AI model config save, admin user role/status changes) require client components — they need local state, transitions, or optimistic updates — but must call the backend with the user's access token. The access token is stored in an `HttpOnly` session cookie and is therefore invisible to client-side JavaScript.

Three approaches were considered:

### Option A — Next.js Route Handler

Create an API route (e.g. `app/api/user/password/route.ts`) that the client fetches. The route handler runs server-side, reads the session via `auth()`, and calls the backend.

**Rejected.** Route handlers are the right tool for browser-facing REST endpoints. Using them for internal UI mutations adds unnecessary indirection (an extra HTTP hop: client → Next.js route → backend) and requires manual error serialisation.

### Option B — Import `lib/api.ts` from a `"use server"` actions file

`lib/api.ts` is marked `"use server"` (makes its exports callable from client components). An actions file imports from it and wraps each call.

**Rejected.** A `"use server"` module calling another `"use server"` module creates a nested server-action chain. The inner call (`auth()` inside `lib/api.ts`) loses the original HTTP request context — cookies are unavailable and `auth()` returns `null`. The access token is never retrieved and backend calls return 401.

### Option C — Inline `auth()` call in each server action ✓

Each server action file calls `auth()` directly to retrieve the session and access token, then makes a single `fetch()` to the backend.

```typescript
"use server";
import { auth } from "@/auth";

export async function changePasswordAction(currentPw: string, newPw: string) {
  const session = await auth();
  const token = (session as any)?.accessToken;
  if (!token) return { error: "Session expired." };
  const res = await fetch(`${process.env.API_URL}/api/auth/me/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
  });
  if (res.status === 204) return {};
  return { error: "..." };
}
```

**Accepted.** `auth()` is reliable in server actions (cookies from `next/headers` are available). The access token never leaves the server. Client components call the action and receive a plain `{ error? }` result — no token handling in the browser.

## Pattern used across the codebase

| Action file | Mutations |
|---|---|
| `app/settings/actions.ts` | `changePasswordAction`, `updateProfileAction` |
| `app/admin/users/actions.ts` | `setRoleAction`, `setActiveAction` |
| `app/admin/ollama/actions.ts` | `saveAiModelsAction` |

`lib/api.ts` (marked `"use server"`) is for server components and layouts only — it is not imported by action files.
