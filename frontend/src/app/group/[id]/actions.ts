"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function inviteMemberAction(
  groupId: string,
  email: string,
  role: string
): Promise<{ token?: string; invite_url?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/groups/${groupId}/members/invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ email, role }),
  });
  if (res.status === 403) return { error: await actionError("GroupPage.OwnerOnly") };
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/group/${groupId}`);
  return await res.json();
}

export async function removeMemberAction(
  groupId: string,
  membershipId: string
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/groups/${groupId}/members/${membershipId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (res.status === 403) return { error: await actionError("GroupPage.OwnerOnly") };
  if (!res.ok && res.status !== 204) return { error: await actionError("Common.RequestFailed", { status: res.status }) };
  revalidatePath(`/group/${groupId}`);
  return {};
}

export async function updateMemberRoleAction(
  groupId: string,
  membershipId: string,
  role: string
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/groups/${groupId}/members/${membershipId}/role`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ role }),
  });
  if (res.status === 403) return { error: await actionError("GroupPage.OwnerOnly") };
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/group/${groupId}`);
  return {};
}

export async function assignPatientAction(
  patientId: string,
  groupId: string
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/patients/${patientId}/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({ group_id: groupId }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/group/${groupId}`);
  return {};
}

export async function removePatientAction(
  patientId: string,
  groupId: string
): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/patients/${patientId}/group`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok && res.status !== 204) return { error: await actionError("Common.RequestFailed", { status: res.status }) };
  revalidatePath(`/group/${groupId}`);
  return {};
}

export async function acceptGroupInviteAction(
  inviteToken: string
): Promise<{ group_id?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/groups/invite/accept?token=${encodeURIComponent(inviteToken)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (res.status === 403) return { error: await actionError("GroupPage.InviteOtherAddress") };
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    return { error: d?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  return await res.json();
}
