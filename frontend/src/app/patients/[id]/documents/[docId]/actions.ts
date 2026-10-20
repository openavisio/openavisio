"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/auth";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

async function getToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function deleteDocumentAction(docId: string, patientId: string): Promise<{ error?: string }> {
  const token = await getToken();
  if (!token) return { error: await actionError("Auth.SessionExpired") };

  const res = await fetch(`${API}/api/documents/${docId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 204) {
    revalidatePath(`/patients/${patientId}/documents`);
    return {};
  }
  return { error: await actionError("Common.DeleteFailed", { status: res.status }) };
}

export async function updateIssuedDateAction(
  docId: string,
  patientId: string,
  issuedDate: string | null,
): Promise<{ error?: string }> {
  const token = await getToken();
  if (!token) return { error: await actionError("Auth.SessionExpired") };

  const res = await fetch(`${API}/api/documents/${docId}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ issued_date: issuedDate }),
  });

  if (!res.ok) return { error: await actionError("Common.UpdateFailed", { status: res.status }) };
  revalidatePath(`/patients/${patientId}/documents/${docId}`);
  return {};
}
