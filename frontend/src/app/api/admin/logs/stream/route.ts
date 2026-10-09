import { auth } from "@/auth";
import { NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

// SSE proxy: the browser connects same-origin (session cookie), we attach the
// backend bearer server-side and pipe the event stream through (issue #51).
export const dynamic = "force-dynamic";

export async function GET() {
  const token = (await auth() as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });

  const upstream = await fetch(`${API_URL}/api/admin/logs/stream`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
    cache: "no-store",
  });
  if (!upstream.ok || !upstream.body) {
    return NextResponse.json({ error: "Upstream error" }, { status: upstream.status || 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
