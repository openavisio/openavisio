"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function consentShareAction(
  patientId: string,
  purposeId: string,
  documentIds: string[],
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  if (documentIds.length === 0) return { error: await actionError("Common.SelectAtLeastOne") };

  const res = await fetch(`${API}/api/patients/${patientId}/sharing/purposes/${purposeId}/consent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ document_ids: documentIds }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}`);
  return {};
}

export async function declineShareAction(
  patientId: string,
  purposeId: string,
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };

  const res = await fetch(`${API}/api/patients/${patientId}/sharing/purposes/${purposeId}/decline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}`);
  return {};
}

export async function revokeShareAction(
  patientId: string,
  shareId: string,
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };

  const res = await fetch(`${API}/api/patients/${patientId}/sharing/shares/${shareId}/revoke`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}`);
  return {};
}
