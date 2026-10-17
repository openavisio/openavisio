"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";

const STEP_KEYS = [
  "StepLanguage",
  "StepOrganization",
  "StepSMTP",
  "StepAdmin",
  "StepPatient",
  "StepDone",
] as const;

interface Props {
  state: WizardState;
  onNext: () => void;
  onBack: () => void;
  onSubmit: () => void;
  submitting: boolean;
  error: string;
  hosted?: boolean;
  children: React.ReactNode;
}

export function WizardShell({ state, onNext, onBack, onSubmit, submitting, error, hosted = false, children }: Props) {
  const t = useTranslations("Setup");
  const { step } = state;
  const isLast = step === 4;
  const isDone = step === 5;
  const first = hosted ? 3 : 0;
  const shown = STEP_KEYS.slice(first, 5);  // the done step has no indicator

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-lg bg-card rounded-2xl shadow-lg overflow-hidden">
        {/* Step indicator */}
        {!isDone && (
          <div className="px-8 pt-6 pb-4">
            <div className="flex justify-center mb-5">
              <Image src="/logo.png" alt="OpenAvisio" width={56} height={56} />
            </div>
            <div className="flex items-center gap-1 mb-4">
              {shown.map((key, n) => {
                const i = first + n;
                return (
                <div key={key} className="flex items-center flex-1">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 transition-colors
                      ${i < step ? "bg-primary text-primary-foreground" : i === step ? "bg-primary text-primary-foreground ring-2 ring-primary/30" : "bg-muted text-muted-foreground"}`}
                  >
                    {i < step ? "✓" : n + 1}
                  </div>
                  {i < 4 && <div className={`h-0.5 flex-1 mx-1 transition-colors ${i < step ? "bg-primary" : "bg-muted"}`} />}
                </div>
                );
              })}
            </div>
            <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {t(hosted && step === 3 ? "StepAccount" : STEP_KEYS[step])}
            </h2>
          </div>
        )}

        {/* Content */}
        <div className="px-8 pb-6">
          {error && (
            <div className="mb-4 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
              {error}
            </div>
          )}
          {children}
        </div>

        {/* Navigation */}
        {!isDone && (
          <div className="flex items-center justify-between px-8 py-4 border-t bg-muted/20">
            <button
              type="button"
              onClick={onBack}
              disabled={step === first}
              className="px-4 py-2 text-sm rounded-lg border hover:bg-muted disabled:opacity-0 disabled:pointer-events-none transition-colors"
            >
              {t("Back")}
            </button>
            <button
              type="button"
              onClick={isLast ? onSubmit : onNext}
              disabled={submitting}
              className="px-5 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 font-medium transition-colors"
            >
              {submitting ? "..." : isLast ? t("Initialize") : t("Next")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
