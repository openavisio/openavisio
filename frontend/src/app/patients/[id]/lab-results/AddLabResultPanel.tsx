"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createObservation } from "@/lib/api";
import { Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

// Common CBC parameter names for quick manual entry (datalist hint only, not enforced).
const CBC_NAMES = [
  "Hämoglobin", "Hämatokrit", "Erythrozyten", "Leukozyten", "Thrombozyten",
  "MCV", "MCH", "MCHC", "RDW", "MPV",
  "Neutrophile", "Lymphozyten", "Monozyten", "Eosinophile", "Basophile",
];

export function AddLabResultPanel({
  patientId,
  children,
}: {
  patientId: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const t = useTranslations("LabResult");
  const tc = useTranslations("Common");
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const [testName, setTestName] = useState("");
  const [valueType, setValueType] = useState<"numeric" | "text">("numeric");
  const [valueNum, setValueNum] = useState("");
  const [valueText, setValueText] = useState("");
  const [unit, setUnit] = useState("");
  const [refLow, setRefLow] = useState("");
  const [refHigh, setRefHigh] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");

  function reset() {
    setTestName("");
    setValueType("numeric");
    setValueNum("");
    setValueText("");
    setUnit("");
    setRefLow("");
    setRefHigh("");
    setDate(new Date().toISOString().slice(0, 10));
    setError("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await createObservation(patientId, {
          category: "lab",
          code_display: testName.trim(),
          value_quantity: valueType === "numeric" && valueNum ? parseFloat(valueNum) : null,
          value_unit: valueType === "numeric" && unit ? unit.trim() : null,
          value_string: valueType === "text" ? valueText.trim() : null,
          ref_low: valueType === "numeric" && refLow ? parseFloat(refLow) : null,
          ref_high: valueType === "numeric" && refHigh ? parseFloat(refHigh) : null,
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
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                {t("TestName")} <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                required
                list="cbc-names"
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                className={inputCls}
                placeholder={t("TestNamePlaceholder")}
              />
              <datalist id="cbc-names">
                {CBC_NAMES.map((n) => <option key={n} value={n} />)}
              </datalist>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("ValueType")}</label>
              <div className="flex gap-3">
                {(["numeric", "text"] as const).map((vt) => (
                  <label key={vt} className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="valueType"
                      value={vt}
                      checked={valueType === vt}
                      onChange={() => setValueType(vt)}
                    />
                    {vt === "numeric" ? t("Numeric") : t("TextType")}
                  </label>
                ))}
              </div>
            </div>

            {valueType === "numeric" ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">
                    {tc("Value")} <span className="text-destructive">*</span>
                  </label>
                  <input
                    type="number"
                    required
                    step="any"
                    value={valueNum}
                    onChange={(e) => setValueNum(e.target.value)}
                    className={inputCls}
                    placeholder="e.g. 5.2"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t("Unit")}</label>
                  <input
                    type="text"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className={inputCls}
                    placeholder="e.g. mmol/L"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t("RefLow")}</label>
                  <input
                    type="number"
                    step="any"
                    value={refLow}
                    onChange={(e) => setRefLow(e.target.value)}
                    className={inputCls}
                    placeholder="e.g. 4.5"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t("RefHigh")}</label>
                  <input
                    type="number"
                    step="any"
                    value={refHigh}
                    onChange={(e) => setRefHigh(e.target.value)}
                    className={inputCls}
                    placeholder="e.g. 11.0"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  {t("Result")} <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={valueText}
                  onChange={(e) => setValueText(e.target.value)}
                  className={inputCls}
                  placeholder="e.g. positive, negative, detected"
                />
              </div>
            )}

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
