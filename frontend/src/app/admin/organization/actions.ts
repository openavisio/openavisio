"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/auth";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

export async function updateOrganizationAction(fields: {
  name?: string;
  description?: string | null;
  default_language?: string;
  is_household?: boolean;  // ADR 046
  // operator's legal details — Impressum (§5 DDG) and controller (Art. 13 GDPR)
  legal_name?: string | null;
  legal_street?: string | null;
  legal_postcode?: string | null;
  legal_city?: string | null;
  legal_country?: string | null;
  legal_email?: string | null;
  legal_phone?: string | null;
  legal_responsible?: string | null;
  legal_vat_id?: string | null;
  legal_register?: string | null;
  dpo_contact?: string | null;
}): Promise<{ error?: string }> {
  const session = await auth();
  const token = (session as any)?.accessToken;
  if (!token) return { error: await actionError("Common.NotAuthenticated") };

  const res = await fetch(`${API}/api/organization`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(fields),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail || "Failed to update organization" };
  }

  revalidatePath("/admin/organization");
  return {};
}
