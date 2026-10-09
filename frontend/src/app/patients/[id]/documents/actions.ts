"use server";

import { revalidatePath } from "next/cache";
import { addDocumentFavorite, removeDocumentFavorite } from "@/lib/api";

export async function toggleDocumentFavoriteAction(
  docId: string,
  patientId: string,
  favorite: boolean,
): Promise<{ error?: string }> {
  try {
    if (favorite) {
      await addDocumentFavorite(docId);
    } else {
      await removeDocumentFavorite(docId);
    }
    revalidatePath(`/patients/${patientId}/documents`);
    return {};
  } catch {
    return { error: "failed" };
  }
}
