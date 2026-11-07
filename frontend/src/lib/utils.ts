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

/** Age in years and months on a date (YYYY-MM or YYYY-MM-DD); a month-only date ignores the day. */
export function ageAt(birth?: string | null, at?: string | null): { y: number; m: number } | null {
  if (!birth || !at) return null;
  const [by, bm, bd] = birth.slice(0, 10).split("-").map(Number);
  const [ay, am, ad] = at.slice(0, 10).split("-").map(Number);
  if (!by || !bm || !ay || !am) return null;
  let months = (ay - by) * 12 + (am - bm);
  if (ad && bd && ad < bd) months -= 1;
  return months < 0 ? null : { y: Math.floor(months / 12), m: months % 12 };
}
