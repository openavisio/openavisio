"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ChevronDown, LayoutGrid, Settings, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { PATIENT_SECTIONS } from "@/lib/patientSections";

// Mobile-only section switcher: the current section name is the nav. Tapping it
// opens a dropdown (anchored right below it) of all the patient's sections, so
// the bottom bar stays calm (ADR 030, #80). Renders nothing off patient pages.
export function PatientSectionSwitcher() {
  const pathname = usePathname();
  const tp = useTranslations("Patient");
  const [open, setOpen] = useState(false);

  const m = pathname.match(/^\/patients\/([^/]+)(?:\/([^/]+))?/);
  const patientId = m && m[1] !== "new" ? m[1] : null;
  if (!patientId) return null;
  const segment = m![2] ?? null; // null => overview

  const items = [
    { segment: null as string | null, href: `/patients/${patientId}`, label: tp("Overview"), Icon: LayoutGrid, tint: "bg-primary/10 text-primary" },
    ...PATIENT_SECTIONS.map((s) => ({ segment: s.segment, href: `/patients/${patientId}/${s.segment}`, label: tp(s.key), Icon: s.Icon, tint: s.tint })),
    { segment: "manage", href: `/patients/${patientId}/manage`, label: tp("Manage"), Icon: Settings, tint: "bg-muted text-muted-foreground" },
  ];
  const current = items.find((i) => i.segment === segment) ?? items[0];

  return (
    <div className="lg:hidden relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left"
      >
        <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${current.tint}`}>
          <current.Icon className="size-4" />
        </span>
        <span className="flex-1 truncate font-semibold">{current.label}</span>
        <ChevronDown className={`size-5 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <>
          {/* backdrop catches outside taps */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="absolute inset-x-0 top-full z-50 mt-2 max-h-[70vh] overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-lg"
            onClick={() => setOpen(false)}
          >
            {items.map((i) => {
              const active = i.segment === current.segment;
              return (
                <Link
                  key={i.href}
                  href={i.href}
                  className={`flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm ${active ? "bg-accent font-semibold" : "hover:bg-accent"}`}
                >
                  <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${i.tint}`}>
                    <i.Icon className="size-4" />
                  </span>
                  <span className="flex-1 truncate">{i.label}</span>
                  {active && <Check className="size-4 shrink-0 text-primary" />}
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
