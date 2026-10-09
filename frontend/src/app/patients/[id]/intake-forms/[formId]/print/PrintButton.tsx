"use client";

import { Printer } from "lucide-react";

export function PrintButton({ label }: { label: string }) {
  return (
    <button onClick={() => window.print()}
      className="mb-6 inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm print:hidden">
      <Printer className="h-4 w-4" />{label}
    </button>
  );
}
