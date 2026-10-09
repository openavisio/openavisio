import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

/** A route handler rather than a server action: an action makes Next refresh the
 *  RSC tree afterwards, which re-suspends the overlay's boundary and tears the
 *  panel out of the DOM mid-interaction. It also hands the client the real
 *  status code, so a 503 can be told from any other failure. */
async function proxy(id: string, init?: RequestInit) {
  const token = (await auth() as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });

  const res = await fetch(`${API_URL}/api/patients/${id}/chat${init ? "" : "/history"}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  return NextResponse.json(await res.json().catch(() => ({})), { status: res.status });
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxy(id);
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxy(id, { method: "POST", body: JSON.stringify(await req.json()) });
}
