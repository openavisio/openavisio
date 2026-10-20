"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { actionError } from "@/lib/action-errors";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export type CalendarFeed = {
  id: string;
  created_at: string;
  revoked_at: string | null;
  last_accessed_at: string | null;
};

export async function listCalendarFeedsAction(patientId: string): Promise<CalendarFeed[]> {
  const t = await token();
  if (!t) return [];
  const res = await fetch(`${API}/api/patients/${patientId}/calendar/feeds`, {
    headers: { Authorization: `Bearer ${t}` },
    cache: "no-store",
  });
  return res.ok ? res.json() : [];
}

export async function createCalendarFeedAction(patientId: string): Promise<{ url?: string; error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/patients/${patientId}/calendar/feeds`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}/calendar`);
  return { url: (await res.json()).url };
}

export async function revokeCalendarFeedAction(patientId: string, feedId: string): Promise<{ error?: string }> {
  const t = await token();
  if (!t) return { error: await actionError("Common.NotAuthenticated") };
  const res = await fetch(`${API}/api/patients/${patientId}/calendar/feeds/${feedId}/revoke`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data?.detail ?? await actionError("Common.RequestFailed", { status: res.status }) };
  }
  revalidatePath(`/patients/${patientId}/calendar`);
  return {};
}
