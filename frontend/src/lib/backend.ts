import { auth } from "@/auth";
import { forwardedFor } from "@/lib/forwarded";

const API_URL = process.env.API_URL || "http://localhost:8000";

// Every server-side call to the backend goes through here, so each one carries the
// visitor's IP for the per-IP limits and the session's token unless it brings its own.
// Not a "use server" module: an export there would be callable from any browser.
export async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!headers.has("Authorization")) {
    const token = (await auth())?.accessToken;
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  for (const [k, v] of Object.entries(await forwardedFor())) headers.set(k, v);
  return fetch(`${API_URL}${path}`, { cache: "no-store", ...init, headers });
}
