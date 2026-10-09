import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.API_URL || "http://localhost:8000";

// auth() is called directly in each handler (not via a helper) — mirrors the
// working document upload route; nesting it can drop the request context here.

// Serve the decrypted photo inline so an <img src> works via the session cookie.
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = ((await auth()) as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${API}/api/patients/${id}/photo`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return NextResponse.json({ error: "Not found" }, { status: res.status });
  return new NextResponse(res.body, {
    headers: {
      "Content-Type": res.headers.get("content-type") || "image/jpeg",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, max-age=60",
    },
  });
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await auth();
  const token = (session as any)?.accessToken ?? null;
  const formData = await req.formData();
  const res = await fetch(`${API}/api/patients/${id}/photo`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    let error = text;
    try { error = JSON.parse(text).detail ?? text; } catch {}
    return NextResponse.json({ error }, { status: res.status });
  }
  return NextResponse.json(await res.json());
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await auth();
  const token = (session as any)?.accessToken ?? null;
  const res = await fetch(`${API}/api/patients/${id}/photo`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return NextResponse.json({ error: "Failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
