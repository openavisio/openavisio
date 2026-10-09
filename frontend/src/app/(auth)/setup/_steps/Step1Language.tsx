"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { WizardState } from "../_hooks/useWizardState";

const LOCALES = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
];

interface Props {
  state: WizardState;
  onLocale: (locale: string) => void;
}

export function Step1Language({ state, onLocale }: Props) {
  const t = useTranslations("Setup");
  const router = useRouter();

  function select(code: string) {
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; SameSite=Lax`;
    onLocale(code);
    router.refresh();
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("ChooseLanguage")}</p>
      <div className="grid grid-cols-1 gap-2">
        {LOCALES.map(({ code, label, flag }) => (
          <button
            key={code}
            type="button"
            onClick={() => select(code)}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors
              ${state.locale === code ? "border-primary bg-primary/5 font-medium" : "hover:bg-muted"}`}
          >
            <span className="text-2xl">{flag}</span>
            <span className="text-sm">{label}</span>
            {state.locale === code && <span className="ml-auto text-primary text-sm">✓</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
