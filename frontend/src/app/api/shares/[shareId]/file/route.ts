import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export const GET = auth(async (req, context: { params: Promise<{ shareId: string }> }) => {
  const { shareId } = await context.params;
  const token = req.auth?.accessToken ?? null;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await backendFetch(`/api/shares/${shareId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Not found" }, { status: res.status });
  }

  const blob = await res.blob();
  const contentType = res.headers.get("content-type") || "application/octet-stream";
  const disposition = res.headers.get("content-disposition") || "attachment";
  return new NextResponse(blob, {
    headers: { "Content-Type": contentType, "Content-Disposition": disposition },
  });
});
