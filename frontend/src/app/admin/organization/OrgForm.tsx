"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { updateOrganizationAction } from "./actions";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

// label/hint are message keys in the Org namespace, not text.
const LEGAL_FIELDS = [
  { key: "legal_name", label: "LegalName", hint: "LegalNameHint", required: true },
  { key: "legal_street", label: "LegalStreet", required: true },
  { key: "legal_postcode", label: "LegalPostcode", required: true },
  { key: "legal_city", label: "LegalCity", required: true },
  { key: "legal_country", label: "LegalCountry" },
  { key: "legal_email", label: "LegalEmail", hint: "LegalEmailHint", required: true },
  { key: "legal_phone", label: "LegalPhone" },
  { key: "legal_responsible", label: "LegalResponsible", hint: "LegalResponsibleHint" },
  { key: "legal_vat_id", label: "LegalVatId", hint: "LegalVatIdHint" },
  { key: "legal_register", label: "LegalRegister", hint: "LegalRegisterHint" },
  { key: "dpo_contact", label: "DpoContact", hint: "DpoContactHint" },
] as const;

type Org = Record<string, string | boolean | null | undefined>;

export function OrgForm({
  initialName,
  initialDescription,
  initialLanguage,
  org,
}: {
  initialName: string;
  initialDescription: string | null;
  initialLanguage: string;
  org: Org;
}) {
  const t = useTranslations("Org");
  const [household, setHousehold] = useState(Boolean(org.is_household));
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription ?? "");
  const [language, setLanguage] = useState(initialLanguage);
  const [legal, setLegal] = useState<Record<string, string>>(
    Object.fromEntries(LEGAL_FIELDS.map((f) => [f.key, (org[f.key] as string) ?? ""])),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    const result = await updateOrganizationAction({
      name: name.trim() || undefined,
      description: description.trim() || null,
      default_language: language,
      is_household: household,
      // empty means "not set" — send null so a wrong entry can actually be cleared
      ...Object.fromEntries(LEGAL_FIELDS.map((f) => [f.key, legal[f.key]?.trim() || null])),
    });
    setSaving(false);
    if (result.error) {
      setError(result.error);
    } else {
      setSaved(true);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("Name")}</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          required
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">{t("Description")}</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none"
        />
      </div>

      {/* ADR 046 */}
      <div className="space-y-2">
        <label className="text-sm font-medium">{t("WhoRuns")}</label>
        <p className="text-xs text-muted-foreground">{t("WhoRunsHint")}</p>
        <div className="flex flex-wrap gap-2">
          {[
            { v: true, label: t("KindHousehold") },
            { v: false, label: t("KindOrganization") },
          ].map((o) => (
            <button
              key={String(o.v)}
              type="button"
              onClick={() => setHousehold(o.v)}
              className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors
                ${household === o.v
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted"
                }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">{t("DefaultLanguage")}</label>
        <p className="text-xs text-muted-foreground">{t("DefaultLanguageHint")}</p>
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => setLanguage(l.code)}
              className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors
                ${language === l.code
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted"
                }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
        <div>
          <h3 className="text-sm font-semibold">{t("LegalTitle")}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{t("LegalHint")}</p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {LEGAL_FIELDS.map((f) => (
            <div key={f.key} className="space-y-1">
              <label className="text-sm font-medium">
                {t(f.label)}
                {"required" in f && f.required && <span className="text-destructive"> *</span>}
              </label>
              <input
                value={legal[f.key] ?? ""}
                onChange={(e) => setLegal({ ...legal, [f.key]: e.target.value })}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
              {"hint" in f && f.hint && <p className="text-xs text-muted-foreground">{t(f.hint)}</p>}
            </div>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {saved && <p className="text-sm text-green-600">{t("Saved")}</p>}

      <button
        type="submit"
        disabled={saving}
        className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
      >
        {saving ? t("Saving") : t("Save")}
      </button>
    </form>
  );
}
