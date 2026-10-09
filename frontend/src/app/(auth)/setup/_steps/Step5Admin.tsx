"use client";

import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";
import { PasswordStrength } from "../_components/PasswordStrength";

interface Props {
  state: WizardState;
  onChange: (admin: Partial<WizardState["admin"]>) => void;
  bootstrapToken: string;
  onBootstrapToken: (token: string) => void;
}

export function Step5Admin({ state, onChange, bootstrapToken, onBootstrapToken }: Props) {
  const t = useTranslations("Setup");
  const { email, password, firstName, lastName } = state.admin;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("BootstrapToken")} *</label>
        <input
          type="password"
          required
          value={bootstrapToken}
          onChange={(e) => onBootstrapToken(e.target.value)}
          autoComplete="off"
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <p className="text-xs text-muted-foreground">{t("BootstrapTokenHint")}</p>
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("AdminEmail")} *</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => onChange({ email: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("AdminPassword")} *</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => onChange({ password: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <PasswordStrength password={password} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-sm font-medium">{t("AdminFirstName")}</label>
          <input
            type="text"
            value={firstName}
            onChange={(e) => onChange({ firstName: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{t("AdminLastName")}</label>
          <input
            type="text"
            value={lastName}
            onChange={(e) => onChange({ lastName: e.target.value })}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>
    </div>
  );
}
