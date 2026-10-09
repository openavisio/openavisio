"use client";

import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";

interface Props {
  state: WizardState;
  onChange: (patient: Partial<WizardState["patient"]>) => void;
  onSkip: () => void;
}

export function Step6Patient({ state, onChange, onSkip }: Props) {
  const t = useTranslations("Setup");
  const { givenName, familyName, birthDate, skip } = state.patient;

  if (skip) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">{t("PatientOptional")}</p>
        <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground text-center">
          {t("PatientSkipped")}
        </div>
        <button
          type="button"
          onClick={() => onChange({ skip: false })}
          className="text-sm text-primary hover:underline"
        >
          {t("PatientAdd")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("PatientOptional")}</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-sm font-medium">{t("PatientGivenName")}</label>
          <input
            type="text"
            value={givenName}
            onChange={(e) => onChange({ givenName: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{t("PatientFamilyName")}</label>
          <input
            type="text"
            value={familyName}
            onChange={(e) => onChange({ familyName: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("PatientBirthDate")}</label>
        <input
          type="date"
          value={birthDate}
          onChange={(e) => onChange({ birthDate: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
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
