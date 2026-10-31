import { headers } from "next/headers";

// The backend's per-IP limits key on X-Forwarded-For. A call from this server carries
// none, so without passing the visitor's on, every visitor shares one budget.
export async function forwardedFor(): Promise<Record<string, string>> {
  try {
    const xff = (await headers()).get("x-forwarded-for");
    return xff ? { "X-Forwarded-For": xff } : {};
  } catch {
    return {};  // outside a request
  }
}
