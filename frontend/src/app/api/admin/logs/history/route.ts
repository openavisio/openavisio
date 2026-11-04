import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const token = (await auth())?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });

  const limit = req.nextUrl.searchParams.get("limit") ?? "500";
  const res = await backendFetch(`/api/admin/logs/history?limit=${encodeURIComponent(limit)}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json().catch(() => []), { status: res.status });
}
