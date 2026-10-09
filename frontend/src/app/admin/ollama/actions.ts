"use server";

import { auth } from "@/auth";

export async function saveAiModelsAction(config: {
  extract_model: string | null;
  classify_model: string | null;
  chat_model: string | null;
  vision_model: string | null;
}): Promise<{ error?: string }> {
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(
    `${process.env.API_URL || "http://localhost:8000"}/api/admin/ollama/models`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(config),
    }
  );

  if (!res.ok) return { error: `Save failed (${res.status}).` };
  return {};
}
