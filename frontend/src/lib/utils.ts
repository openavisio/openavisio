import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined, locale?: string): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString(locale);
  } catch {
    return dateStr;
  }
}

export function formatDose(m: { dosage_text: string | null; dose_quantity: number | null; dose_unit: string | null }): string {
  return m.dosage_text || (m.dose_quantity ? `${m.dose_quantity} ${m.dose_unit || ""}`.trim() : "");
}

export function statusBadgeColor(status: string): string {
  const map: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    completed: "bg-blue-100 text-blue-800",
    stopped: "bg-gray-100 text-gray-800",
    failed: "bg-red-100 text-red-800",
    pending: "bg-yellow-100 text-yellow-800",
    extracted: "bg-purple-100 text-purple-800",
    verified: "bg-green-100 text-green-800",
    resolved: "bg-gray-100 text-gray-800",
    revoked: "bg-red-100 text-red-800",
  };
  return map[status?.toLowerCase()] ?? "bg-gray-100 text-gray-800";
}
