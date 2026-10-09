import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { signChallenge } from "@/lib/passkey-challenge";

const API = process.env.API_URL || "http://localhost:8000";

export async function GET() {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await fetch(`${API}/api/auth/passkey/register/begin`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Failed to begin registration" }, { status: 500 });
  }

  const options = await res.json();
  const signed = signChallenge(options.challenge, process.env.NEXTAUTH_SECRET!);

  const response = NextResponse.json(options);
  response.cookies.set("passkey-challenge", signed, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    maxAge: 300,
    path: "/",
  });
  return response;
}
