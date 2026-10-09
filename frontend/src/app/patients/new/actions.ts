"use server";

import { auth } from "@/auth";

const API = process.env.API_URL || "http://localhost:8000";

export async function createPatientAction(data: {
  given_name: string;
  family_name: string;
  birth_date?: string;
  gender?: string;
  identifier?: string;
}): Promise<{ id?: string; error?: string }> {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    return { error: detail?.detail ?? `Failed to create patient (${res.status}).` };
  }

  const patient = await res.json();
  return { id: patient.id };
}
