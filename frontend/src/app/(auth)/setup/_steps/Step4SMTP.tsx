"use client";

import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";

interface Props {
  state: WizardState;
  onChange: (smtp: Partial<WizardState["smtp"]>) => void;
  onSkip: () => void;
}

export function Step4SMTP({ state, onChange, onSkip }: Props) {
  const t = useTranslations("Setup");
  const { host, port, user, password, from, skip } = state.smtp;

  if (skip) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">{t("SMTPOptional")}</p>
        <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground text-center">
          {t("SMTPSkipped")}
        </div>
        <button
          type="button"
          onClick={() => onChange({ skip: false })}
          className="text-sm text-primary hover:underline"
        >
          {t("SMTPConfigure")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("SMTPOptional")}</p>
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2 space-y-1">
          <label className="text-sm font-medium">{t("SMTPHost")}</label>
          <input
            type="text"
            value={host}
            onChange={(e) => onChange({ host: e.target.value })}
            placeholder="smtp.example.com"
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{t("SMTPPort")}</label>
          <input
            type="number"
            value={port}
            onChange={(e) => onChange({ port: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>
      {[
        { field: "user", label: t("SMTPUser"), type: "text" },
        { field: "password", label: t("SMTPPassword"), type: "password" },
        { field: "from", label: t("SMTPFrom"), type: "email" },
      ].map(({ field, label, type }) => (
        <div key={field} className="space-y-1">
          <label className="text-sm font-medium">{label}</label>
          <input
            type={type}
            value={(state.smtp as any)[field]}
            onChange={(e) => onChange({ [field]: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      ))}
      <button
        type="button"
        onClick={onSkip}
        className="text-sm text-muted-foreground hover:text-foreground hover:underline"
      >
        {t("Skip")}
      </button>
    </div>
  );
}
