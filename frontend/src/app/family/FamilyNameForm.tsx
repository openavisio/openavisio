"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { updateOrganizationAction } from "../admin/organization/actions";

// Only name and language: the Impressum fields and the household switch are not the family's (ADR 052).
export function FamilyNameForm({ initialName, initialLanguage }: { initialName: string; initialLanguage: string }) {
  const t = useTranslations("Family");
  const [name, setName] = useState(initialName);
  const [language, setLanguage] = useState(initialLanguage);
  const [pending, start] = useTransition();
  const [state, setState] = useState<"" | "saved" | "failed">("");
  const input = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    start(async () => {
      const r = await updateOrganizationAction({ name: name.trim() || undefined, default_language: language });
      setState(r.error ? "failed" : "saved");
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4 max-w-sm">
      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="family-name">{t("Name")}</label>
        <input id="family-name" required value={name} onChange={(e) => { setName(e.target.value); setState(""); }} className={input} />
      </div>
      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="family-lang">{t("Language")}</label>
        <select id="family-lang" value={language} onChange={(e) => { setLanguage(e.target.value); setState(""); }} className={input}>
          <option value="de">Deutsch</option>
          <option value="en">English</option>
        </select>
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={pending}
          className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
          {t("Save")}
        </button>
        {state === "saved" && <span className="text-sm text-green-600">{t("Saved")}</span>}
        {state === "failed" && <span className="text-sm text-destructive">{t("Failed")}</span>}
      </div>
    </form>
  );
}
