"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/auth";

const API = process.env.API_URL || "http://localhost:8000";

export type LicenseInfo = {
  tier: string;
  has_license: boolean;
  is_grace_period: boolean;
  issued_to: string | null;
  expires_at: string | null;
  grace_ends_at: string | null;
};

export async function uploadLicenseAction(token: string): Promise<{ error?: string; info?: LicenseInfo }> {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;
  if (!accessToken) return { error: "Not authenticated" };

  const res = await fetch(`${API}/api/admin/license`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ token: token.trim() }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail || "Failed to upload license" };
  }

  revalidatePath("/admin/license");
  return { info: await res.json() };
}

const PERSONAL_INFO: LicenseInfo = {
  tier: "personal",
  has_license: false,
  is_grace_period: false,
  issued_to: null,
  expires_at: null,
  grace_ends_at: null,
};

export async function deleteLicenseAction(): Promise<{ error?: string; info?: LicenseInfo }> {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;
  if (!accessToken) return { error: "Not authenticated" };

  const res = await fetch(`${API}/api/admin/license`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail || "Failed to remove license" };
  }

  revalidatePath("/admin/license");
  return { info: PERSONAL_INFO };
}
