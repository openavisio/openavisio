import { auth } from "@/auth";
import { NextResponse } from "next/server";

// A PDF page as PNG for phones; always image/png, never the uploaded type.
export const GET = auth(async (req, context) => {
  const { docId, page } = await (context as { params: Promise<{ docId: string; page: string }> }).params;
  const token = (req.auth as { accessToken?: string } | null)?.accessToken;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const apiUrl = process.env.API_URL || "http://localhost:8000";
  const res = await fetch(
    `${apiUrl}/api/documents/${encodeURIComponent(docId)}/pages/${encodeURIComponent(page)}` +
      `?width=${encodeURIComponent(req.nextUrl.searchParams.get("width") ?? "1200")}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok) return NextResponse.json({ error: "Not found" }, { status: res.status });
  return new NextResponse(await res.blob(), {
    headers: {
      "Content-Type": "image/png",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, max-age=86400",
      "X-Page-Count": res.headers.get("X-Page-Count") ?? "1",
    },
  });
});
