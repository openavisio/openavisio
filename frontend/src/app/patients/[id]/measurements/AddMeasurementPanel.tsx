"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createObservation } from "@/lib/api";
import { Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { MEASUREMENT_TYPES as TYPES, measurementLabel } from "@/lib/measurementTypes";


const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

export function AddMeasurementPanel({
  patientId,
  children,
}: {
  patientId: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const t = useTranslations("Measurement");
  const tc = useTranslations("Common");
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const [typeCode, setTypeCode] = useState<string>(TYPES[0].code);
  const [value, setValue] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");

  const selectedType = TYPES.find((t) => t.code === typeCode)!;

  function reset() {
    setTypeCode(TYPES[0].code);
    setValue("");
    setDate(new Date().toISOString().slice(0, 10));
    setError("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await createObservation(patientId, {
          category: "measurement",
          code: selectedType.code,
          code_display: selectedType.display,
          value_quantity: parseFloat(value),
          value_unit: selectedType.unit,
          effective_date_time: date,
        });
        reset();
        setOpen(false);
        router.refresh();
      } catch {
        setError(tc("SaveError"));
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
          {t("Add")}
        </button>
      </div>

      {open && (
        <div className="rounded-xl border bg-card p-4 mt-4">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold">{t("Add")}</span>
            <button
              onClick={() => { reset(); setOpen(false); }}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  {tc("Type")} <span className="text-destructive">*</span>
                </label>
                <select
                  value={typeCode}
                  onChange={(e) => setTypeCode(e.target.value)}
                  className={inputCls}
                >
                  {/* the option text is translated; code_display stays canonical English */}
                  {TYPES.map((mt) => (
                    <option key={mt.code} value={mt.code}>{measurementLabel(t, mt.code, mt.display)}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  {tc("Value")} ({selectedType.unit}) <span className="text-destructive">*</span>
                </label>
                <input
                  type="number"
                  required
                  step="any"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className={inputCls}
                  placeholder="e.g. 70"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                {tc("Date")} <span className="text-destructive">*</span>
              </label>
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className={inputCls}
              />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {pending ? tc("Saving") : tc("Save")}
              </button>
              <button
                type="button"
                onClick={() => { reset(); setOpen(false); }}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                {tc("Cancel")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
