"use server";

import { auth } from "@/auth";
import { redirect } from "next/navigation";

const API = process.env.API_URL || "http://localhost:8000";

export async function erasePatientAction(patientId: string, confirmName: string) {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/${patientId}/erase`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ confirm_name: confirmName }),
  });

  if (res.status === 422) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? "Confirmation name does not match." };
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? `Request failed (${res.status}).` };
  }

  redirect("/patients");
}
