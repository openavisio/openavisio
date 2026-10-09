import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  const session = await auth();
  const token = (session as any)?.accessToken ?? null;

  const apiUrl = process.env.API_URL || "http://localhost:8000";
  const formData = await req.formData();

  const res = await fetch(
    `${apiUrl}/api/patients/${patientId}/documents/upload`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }
  );

  if (!res.ok) {
    const text = await res.text();
    let error = text;
    try { error = JSON.parse(text).detail ?? text; } catch {}
    return NextResponse.json({ error }, { status: res.status });
  }

  return NextResponse.json(await res.json());
}
