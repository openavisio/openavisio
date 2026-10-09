"use client";

import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";

interface Props {
  state: WizardState;
  onChange: (org: Partial<WizardState["org"]>) => void;
}

export function Step2Organization({ state, onChange }: Props) {
  const t = useTranslations("Setup");
  const household = state.org.isHousehold;
  return (
    <div className="space-y-4">
      {/* ADR 046: the answer decides whether this person ever sees Groups,
          Sharing Purposes and user management. */}
      <div className="grid gap-2 sm:grid-cols-2">
        {[
          { v: true, title: t("KindHousehold"), hint: t("KindHouseholdHint") },
          { v: false, title: t("KindOrganization"), hint: t("KindOrganizationHint") },
        ].map((o) => (
          <button
            key={String(o.v)}
            type="button"
            onClick={() => onChange({ isHousehold: o.v })}
            aria-pressed={household === o.v}
            className={`rounded-lg border p-3 text-left transition-colors ${
              household === o.v ? "border-primary ring-2 ring-primary" : "hover:bg-accent"
            }`}
          >
            <span className="block text-sm font-medium">{o.title}</span>
            <span className="block text-xs text-muted-foreground">{o.hint}</span>
          </button>
        ))}
      </div>
      {household ? null : (
      <>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("OrgName")} *</label>
        <input
          type="text"
          required
          value={state.org.name}
          onChange={(e) => onChange({ name: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("OrgDescription")}</label>
        <textarea
          rows={3}
          value={state.org.description}
          onChange={(e) => onChange({ description: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
        />
      </div>
      </>
      )}
    </div>
  );
}
