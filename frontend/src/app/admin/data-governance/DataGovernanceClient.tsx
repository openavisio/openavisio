"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";

type Category = {
  code: string;
  label: string;
  is_builtin: boolean;
  lawful_basis: string | null;
  retention_days: number | null;
};

const BASES = [
  "",
  "art9_healthcare",
  "consent",
  "legitimate_interest",
  "legal_obligation",
  "vital_interest",
  "contract",
  "public_task",
];

export function DataGovernanceClient({ categories: initial }: { categories: Category[] }) {
  const t = useTranslations("AdminGovernance");
  const tc = useTranslations("Common");
  const [cats, setCats] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [savedCode, setSavedCode] = useState<string | null>(null);
  const [error, setError] = useState("");

  function patch(code: string, p: Partial<Category>) {
    setCats((cs) => cs.map((c) => (c.code === code ? { ...c, ...p } : c)));
  }

  function save(cat: Category) {
    setError("");
    setSavedCode(null);
    startTransition(async () => {
      const res = await fetch(`/api/admin/data-categories/${cat.code}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lawful_basis: cat.lawful_basis || null,
          retention_days: cat.retention_days ?? null,
        }),
      });
      if (!res.ok) {
        setError(t("SaveFailed", { label: cat.label }));
        return;
      }
      setSavedCode(cat.code);
      setTimeout(() => setSavedCode(null), 2000);
    });
  }

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50">
        <div className="font-medium text-sm">{t("Categories")}</div>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t("CategoriesHint")}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("Category")}</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("LawfulBasis")}</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("RetentionDays")}</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {cats.map((cat) => (
              <tr key={cat.code}>
                <td className="px-4 py-2 font-medium whitespace-nowrap">{cat.label}</td>
                <td className="px-4 py-2">
                  <select
                    value={cat.lawful_basis ?? ""}
                    onChange={(e) => patch(cat.code, { lawful_basis: e.target.value || null })}
                    className="rounded-lg border bg-background px-2 py-1 text-sm"
                  >
                    {BASES.map((b) => (
                      <option key={b} value={b}>{t(`Basis_${b || "none"}`)}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    min={1}
                    value={cat.retention_days ?? ""}
                    onChange={(e) => patch(cat.code, { retention_days: e.target.value ? Number(e.target.value) : null })}
                    placeholder="∞"
                    className="w-24 rounded-lg border bg-background px-2 py-1 text-sm"
                  />
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => save(cat)}
                    disabled={pending}
                    className="rounded-lg border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                  >
                    {savedCode === cat.code ? t("Saved") : tc("Save")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error && <p className="px-4 py-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}
