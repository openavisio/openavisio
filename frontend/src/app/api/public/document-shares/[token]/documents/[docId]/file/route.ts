import { NextRequest, NextResponse } from "next/server";

// Public, unauthenticated proxy for a shared document file (ADR-021).
// Forwards the recipient's IP + user-agent so the backend can audit access.
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ token: string; docId: string }> },
) {
  const { token, docId } = await context.params;
  const download = req.nextUrl.searchParams.get("download");
  const apiUrl = process.env.API_URL || "http://localhost:8000";

  const fwd = req.headers.get("x-forwarded-for") ?? "";
  const ua = req.headers.get("user-agent") ?? "";

  const qs = download ? "?download=true" : "";
  const res = await fetch(
    `${apiUrl}/api/public/document-shares/${encodeURIComponent(token)}/documents/${docId}/file${qs}`,
    { headers: { "X-Forwarded-For": fwd, "User-Agent": ua }, cache: "no-store" },
  );

  if (!res.ok) {
    return NextResponse.json({ error: "Not available" }, { status: res.status });
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") || "";
  const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? docId;
  // Force download + block MIME sniffing (same-origin stored-XSS guard).
  return new NextResponse(blob, {
    headers: {
      "Content-Type": res.headers.get("content-type") || "application/octet-stream",
      "Content-Disposition": `attachment; filename="${String(filename).replace(/"/g, "")}"`,
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}
