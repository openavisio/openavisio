import { auth } from "@/auth";
import { NextResponse } from "next/server";

export const GET = auth(async (req, context) => {
  const { purposeId } = await (context as any).params;
  const token = (req.auth as any)?.accessToken ?? null;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const apiUrl = process.env.API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/sharing-purposes/${purposeId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Not found" }, { status: res.status });
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") || "attachment";
  return new NextResponse(blob, {
    headers: { "Content-Type": "application/zip", "Content-Disposition": disposition },
  });
});
