import { NextResponse } from "next/server";
import { signChallenge } from "@/lib/passkey-challenge";
import { backendFetch } from "@/lib/backend";

export async function GET() {
  const res = await backendFetch(`/api/auth/passkey/authenticate/begin`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Failed to begin authentication" }, { status: 500 });
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
