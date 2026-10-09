"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function grantAccessAction(
  patientId: string,
  email: string,
  accessLevel: string,
  expiresAt?: string,
  purpose?: string,
  relationship?: string,
  isLegalRepresentative?: boolean,
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/${patientId}/access`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ email, access_level: accessLevel, expires_at: expiresAt || null, purpose: purpose || null, relationship: relationship || null, is_legal_representative: !!isLegalRepresentative }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? `Failed (${res.status}).` };
  }

  revalidatePath(`/patients/${patientId}`);
  return {};
}

export async function createCaregiverInviteAction(
  patientId: string,
  email: string | null,
  accessLevel: string
): Promise<{ token?: string; invite_url?: string; registration_url?: string | null; error?: string }> {
  const t = await token();
  if (!t) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/${patientId}/caregiver-invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ email: email || null, access_level: accessLevel }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? `Failed (${res.status}).` };
  }

  const data = await res.json();
  revalidatePath(`/patients/${patientId}`);
  return { token: data.token, invite_url: data.invite_url, registration_url: data.registration_url };
}

export async function acceptCaregiverInviteAction(
  inviteToken: string
): Promise<{ patient_id?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/caregiver-invite/accept?token=${encodeURIComponent(inviteToken)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? `Failed (${res.status}).` };
  }

  return await res.json();
}

export async function updateAccessAction(
  grantId: string,
  patientId: string,
  fields: { access_level?: string; expires_at?: string | null; purpose?: string | null; relationship?: string | null; is_legal_representative?: boolean },
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/access/${grantId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify(fields),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? `Failed (${res.status}).` };
  }

  revalidatePath(`/patients/${patientId}`);
  return {};
}

export async function revokeAccessAction(
  patientId: string,
  grantId: string
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/access/${grantId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${t}` },
  });

  if (!res.ok && res.status !== 204) {
    return { error: `Failed to revoke access (${res.status}).` };
  }

  revalidatePath(`/patients/${patientId}`);
  return {};
}

export async function listUserDirectoryAction(): Promise<{ email: string; name?: string | null }[]> {
  const t = await token();
  if (!t) return [];
  const res = await fetch(`${API}/api/users/directory`, {
    headers: { Authorization: `Bearer ${t}` },
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}
