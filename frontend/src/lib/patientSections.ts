import {
  Activity,
  FileText,
  Pill,
  ClipboardList,
  Ruler,
  FlaskConical,
  Calendar,
  Receipt,
  BadgeCheck,
  Siren,
  HandHeart,
  MessageSquareText,
  ClipboardPen,
  type LucideIcon,
} from "lucide-react";

// Single source for a patient's sections — used by the overview tiles and the
// contextual sidebar nav (#77). `key` maps to the `Patient` message namespace.
// `tint` gives each section its own colour so the overview reads warm, not
// clinical (tester feedback). Full static class strings so Tailwind keeps them.
export const PATIENT_SECTIONS: { key: string; segment: string; Icon: LucideIcon; tint: string }[] = [
  { key: "Dashboard", segment: "dashboard", Icon: Activity, tint: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  { key: "EmergencyPlan", segment: "emergency-plan", Icon: Siren, tint: "bg-red-500/10 text-red-600 dark:text-red-400" },
  { key: "CareNotes", segment: "care-notes", Icon: HandHeart, tint: "bg-pink-500/10 text-pink-600 dark:text-pink-400" },
  { key: "CarerUpdates", segment: "carer-updates", Icon: MessageSquareText, tint: "bg-lime-500/10 text-lime-700 dark:text-lime-400" },
  { key: "IntakeForms", segment: "intake-forms", Icon: ClipboardPen, tint: "bg-sky-500/10 text-sky-600 dark:text-sky-400" },
  { key: "Documents", segment: "documents", Icon: FileText, tint: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  { key: "Medications", segment: "medications", Icon: Pill, tint: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  { key: "Conditions", segment: "conditions", Icon: ClipboardList, tint: "bg-violet-500/10 text-violet-600 dark:text-violet-400" },
  { key: "Measurements", segment: "measurements", Icon: Ruler, tint: "bg-rose-500/10 text-rose-600 dark:text-rose-400" },
  { key: "LabResults", segment: "lab-results", Icon: FlaskConical, tint: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  { key: "Expenses", segment: "expenses", Icon: Receipt, tint: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400" },
  { key: "Einstufung", segment: "einstufung", Icon: BadgeCheck, tint: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
  { key: "Calendar", segment: "calendar", Icon: Calendar, tint: "bg-teal-500/10 text-teal-600 dark:text-teal-400" },
];
