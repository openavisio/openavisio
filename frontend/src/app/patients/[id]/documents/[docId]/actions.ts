"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/auth";

const API = process.env.API_URL || "http://localhost:8000";

async function getToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function deleteDocumentAction(docId: string, patientId: string): Promise<{ error?: string }> {
  const token = await getToken();
  if (!token) return { error: "Session expired." };

  const res = await fetch(`${API}/api/documents/${docId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 204) {
    revalidatePath(`/patients/${patientId}/documents`);
    return {};
  }
  return { error: `Delete failed (${res.status}).` };
}

export async function updateIssuedDateAction(
  docId: string,
  patientId: string,
  issuedDate: string | null,
): Promise<{ error?: string }> {
  const token = await getToken();
  if (!token) return { error: "Session expired." };

  const res = await fetch(`${API}/api/documents/${docId}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ issued_date: issuedDate }),
  });

  if (!res.ok) return { error: `Update failed (${res.status}).` };
  revalidatePath(`/patients/${patientId}/documents/${docId}`);
  return {};
}
