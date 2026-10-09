import { auth } from "@/auth";
import { NextResponse } from "next/server";

export const GET = auth(async (req, context) => {
  const { docId } = await (context as any).params;
  const token = (req.auth as any)?.accessToken ?? null;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const apiUrl = process.env.API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/documents/${docId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Not found" }, { status: res.status });
  }

  const blob = await res.blob();
  const contentType = res.headers.get("content-type") || "application/octet-stream";
  const disposition = res.headers.get("content-disposition") || "";
  const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? docId;
  // Force download + block MIME sniffing: files are served from the app origin,
  // so an inline text/html or SVG upload would otherwise execute in-origin.
  return new NextResponse(blob, {
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename="${String(filename).replace(/"/g, "")}"`,
      "X-Content-Type-Options": "nosniff",
    },
  });
});
