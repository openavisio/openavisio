import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.API_URL || "http://localhost:8000";

// The ZIP export (ADR 052), streamed through so a plain <a href download> works via the session cookie.
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = ((await auth()) as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${API}/api/patients/${id}/export/zip`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return NextResponse.json({ error: "Not found" }, { status: res.status });
  return new NextResponse(res.body, {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": res.headers.get("content-disposition") || "attachment",
    },
  });
}
