import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET() {
  const token = (await auth())?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });

  const res = await backendFetch(`/api/admin/logs/tasks`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json().catch(() => []), { status: res.status });
}
