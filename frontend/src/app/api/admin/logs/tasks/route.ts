import { auth } from "@/auth";
import { NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET() {
  const token = (await auth() as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });

  const res = await fetch(`${API_URL}/api/admin/logs/tasks`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json().catch(() => []), { status: res.status });
}
