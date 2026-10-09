"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";

const API = process.env.API_URL || "http://localhost:8000";

async function adminFetch(path: string, body: unknown) {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) return { error: `Request failed (${res.status}).` };
  revalidatePath("/admin/users");
  return {};
}

export async function setRoleAction(userId: string, role: string) {
  return adminFetch(`/api/admin/users/${userId}/role`, { role });
}

export async function setActiveAction(userId: string, isActive: boolean) {
  return adminFetch(`/api/admin/users/${userId}/active`, { is_active: isActive });
}

export async function eraseUserAction(userId: string, confirmEmail: string) {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${process.env.API_URL || "http://localhost:8000"}/api/admin/users/${userId}/erase`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ confirm_email: confirmEmail }),
  });

  if (res.status === 409) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail?.message ?? "User owns Patients that must be erased first." };
  }
  if (res.status === 422) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? "Confirmation email does not match." };
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? `Request failed (${res.status}).` };
  }

  revalidatePath("/admin/users");
  return {};
}
