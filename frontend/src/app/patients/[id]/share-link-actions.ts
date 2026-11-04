"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { actionError } from "@/lib/action-errors";
import { backendFetch } from "@/lib/backend";

async function token() {
  const session = await auth();
  return session?.accessToken as string | undefined;
}

export async function createShareLinkAction(
  patientId: string,
  documentIds: string[],
  expiryDays: number,
  handout?: { variant: string; exclude: string[]; lang: string },
): Promise<{ url?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  if (documentIds.length === 0 && !handout) return { error: await actionError("Common.SelectAtLeastOne") };

  const res = await backendFetch(`/api/patients/${patientId}/share-links`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ document_ids: documentIds, expiry_days: expiryDays, handout }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}`);
  return { url: (await res.json()).url };
}

export async function addShareLinkDocumentsAction(
  patientId: string,
  linkId: string,
  documentIds: string[],
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  if (documentIds.length === 0) return { error: await actionError("Common.SelectAtLeastOne") };

  const res = await backendFetch(`/api/patients/${patientId}/share-links/${linkId}/documents`, {
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

export async function revokeShareLinkAction(
  patientId: string,
  linkId: string,
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };

  const res = await backendFetch(`/api/patients/${patientId}/share-links/${linkId}/revoke`, {
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
