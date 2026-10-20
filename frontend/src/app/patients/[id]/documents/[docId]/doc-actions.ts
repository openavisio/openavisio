"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function setCorrespondentAction(
  docId: string,
  patientId: string,
  correspondentId: string | null
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };

  const res = await fetch(`${API}/api/documents/${docId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ correspondent_id: correspondentId }),
  });

  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }

  revalidatePath(`/patients/${patientId}/documents/${docId}`);
  return {};
}

export async function createCorrespondentAction(
  name: string
): Promise<{ id?: string; name?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };

  const res = await fetch(`${API}/api/correspondents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ name }),
  });

  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }

  return await res.json();
}
