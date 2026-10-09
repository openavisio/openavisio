"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { createMedication } from "@/lib/api";
import { Plus, X } from "lucide-react";

const UNITS = ["Tablette", "Kapsel", "ml", "Tropfen", "Pflaster", "Injektion", "Spray", "IE"];

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

export function AddMedicationPanel({ patientId, children }: { patientId: string; children: React.ReactNode }) {
  const t = useTranslations("Med");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const [name, setName] = useState("");
  const [unit, setUnit] = useState("Tablette");
  const [customUnit, setCustomUnit] = useState("");
  const [morning, setMorning] = useState("");
  const [noon, setNoon] = useState("");
  const [evening, setEvening] = useState("");
  const [night, setNight] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setName("");
    setUnit("Tablette");
    setCustomUnit("");
    setMorning("");
    setNoon("");
    setEvening("");
    setNight("");
    setStartDate("");
    setNote("");
    setError("");
  }

  function close() {
    reset();
    setOpen(false);
  }

  function composeDosage(): string | undefined {
    const slots = [morning, noon, evening, night];
    const hasAny = slots.some((v) => v !== "" && parseFloat(v) !== 0);
    if (!hasAny) return undefined;
    const schedule = slots.map((v) => (v === "" ? "0" : v)).join("-");
    const resolvedUnit = unit === "Other" ? customUnit.trim() : unit;
    return resolvedUnit ? `${schedule} ${resolvedUnit}` : schedule;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const dosage = composeDosage();
    const resolvedUnit = unit === "Other" ? customUnit.trim() : unit;
    startTransition(async () => {
      try {
        await createMedication(patientId, {
          medication_display: name,
          dosage_text: dosage,
          dose_unit: dosage ? resolvedUnit : undefined,
          effective_start: startDate || undefined,
          effective_end: endDate || undefined,
          note: note || undefined,
        });
        close();
        router.refresh();
      } catch {
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
                <label className="text-sm font-medium">
                  {t("Name")} <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={inputCls}
                  placeholder={t("NamePlaceholder")}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Unit")}</label>
                <select
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  className={inputCls}
                >
                  {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
                  <option value="Other">{t("Other")}</option>
                </select>
                {unit === "Other" && (
                  <input
                    type="text"
                    value={customUnit}
                    onChange={(e) => setCustomUnit(e.target.value)}
                    className={inputCls}
                    placeholder={t("UnitPlaceholder")}
                  />
                )}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium block mb-1.5">{t("DosageLabel")}</label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: t("Morning"), value: morning, set: setMorning },
                  { label: t("Noon"), value: noon, set: setNoon },
                  { label: t("Evening"), value: evening, set: setEvening },
                  { label: t("Night"), value: night, set: setNight },
                ].map(({ label, value, set }) => (
                  <div key={label} className="space-y-1">
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={value}
                      onChange={(e) => set(e.target.value)}
                      className={inputCls}
                      placeholder="0"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("StartDateLabel")}</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("EndDateLabel")}</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className={inputCls}
                />
                <p className="text-xs text-muted-foreground">{t("EndDateHint")}</p>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("NoteLabel")}</label>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className={inputCls}
                placeholder={t("NotePlaceholder")}
              />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {pending ? t("Adding") : t("Submit")}
              </button>
              <button
                type="button"
                onClick={close}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                {t("Cancel")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
