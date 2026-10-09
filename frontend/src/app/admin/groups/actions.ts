"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";

const API = process.env.API_URL || "http://localhost:8000";

export async function createGroupAction(name: string): Promise<{ id?: string; error?: string }> {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/groups`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name }),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    return { error: detail?.detail ?? `Failed to create group (${res.status}).` };
  }

  const group = await res.json();
  revalidatePath("/admin/groups");
  return { id: group.id };
}
