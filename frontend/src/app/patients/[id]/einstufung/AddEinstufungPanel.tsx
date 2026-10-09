"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { createEinstufung } from "@/lib/api";
import { Plus, X } from "lucide-react";
import { MODULES } from "@/lib/einstufung";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

export function AddEinstufungPanel({ patientId, children }: { patientId: string; children: React.ReactNode }) {
  const t = useTranslations("Einstufung");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const [grade, setGrade] = useState("2");
  const [points, setPoints] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [authority, setAuthority] = useState("");
  const [fileRef, setFileRef] = useState("");
  const [modules, setModules] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  function close() {
    setGrade("2"); setPoints(""); setValidFrom(""); setValidUntil("");
    setAuthority(""); setFileRef(""); setModules({}); setError("");
    setOpen(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const moduleValues = Object.fromEntries(
      Object.entries(modules).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]),
    );
    startTransition(async () => {
      try {
        await createEinstufung(patientId, {
          pflegegrad: grade ? Number(grade) : undefined,
          total_points: points ? Number(points) : undefined,
          valid_from: validFrom || undefined,
          valid_until: validUntil || undefined,
          authority: authority || undefined,
          file_reference: fileRef || undefined,
          ...moduleValues,
        });
        close();
        router.refresh();
      } catch {
        // The backend refuses a grade outside 1..5 and a module over its statutory
        // cap; both mean the numbers were read off the wrong column.
        setError(t("AddError"));
      }
    });
  }

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between">
        {children}
        <button
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("AddTitle")}
        </button>
      </div>

      {open && (
        <div className="rounded-xl border bg-card p-4 mt-4">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold">{t("AddTitle")}</span>
            <button onClick={close} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Grade")}</label>
                <select value={grade} onChange={(e) => setGrade(e.target.value)} className={inputCls}>
                  {[1, 2, 3, 4, 5].map((g) => (
                    <option key={g} value={g}>{t("GradeValue", { grade: g })}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Points")}</label>
                <input type="number" min="0" max="100" step="0.5" value={points}
                  onChange={(e) => setPoints(e.target.value)} className={inputCls} placeholder="42.5" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("ValidFrom")}</label>
                <input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("ValidUntil")}</label>
                <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className={inputCls} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Authority")}</label>
                <input type="text" value={authority} onChange={(e) => setAuthority(e.target.value)} className={inputCls} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("FileReference")}</label>
                <input type="text" value={fileRef} onChange={(e) => setFileRef(e.target.value)} className={inputCls} />
              </div>
            </div>

            <details className="rounded-lg border px-3 py-2">
              <summary className="text-sm font-medium cursor-pointer">{t("ModulesOptional")}</summary>
              <p className="text-xs text-muted-foreground mt-2">{t("ModulesEntryHint")}</p>
              <div className="grid grid-cols-2 gap-3 mt-3">
                {MODULES.map(({ key, cap }) => (
                  <div key={key} className="space-y-1.5">
                    <label className="text-xs font-medium">
                      {t(`module.${key}`)} <span className="text-muted-foreground">({t("OfCap", { cap })})</span>
                    </label>
                    <input type="number" min="0" max={cap} step="0.5" value={modules[key] ?? ""}
                      onChange={(e) => setModules((m) => ({ ...m, [key]: e.target.value }))}
                      className={inputCls} />
                  </div>
                ))}
              </div>
            </details>

            <div className="flex items-center gap-3 pt-1">
              <button type="submit" disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
                {pending ? t("Adding") : t("Submit")}
              </button>
              <button type="button" onClick={close}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
                {t("Cancel")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
