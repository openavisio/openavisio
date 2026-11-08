import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export const GET = auth(async (req, context: { params: Promise<{ purposeId: string }> }) => {
  const { purposeId } = await context.params;
  const token = req.auth?.accessToken ?? null;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await backendFetch(`/api/sharing-purposes/${purposeId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Not found" }, { status: res.status });
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") || "attachment";
  return new NextResponse(blob, {
    headers: { "Content-Type": res.headers.get("content-type") || "application/zip", "Content-Disposition": disposition },
  });
});
