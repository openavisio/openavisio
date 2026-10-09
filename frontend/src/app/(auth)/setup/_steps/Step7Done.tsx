"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

export function Step7Done({ recoveryCode }: { recoveryCode?: string }) {
  const t = useTranslations("Setup");
  const router = useRouter();
  const [noted, setNoted] = useState(false);
  const [copied, setCopied] = useState(false);

  function goToLogin() {
    document.cookie = "setup_complete=1; path=/; max-age=2147483647; SameSite=Lax";
    router.push("/login");
  }

  return (
    <div className="py-8 text-center space-y-4">
      <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto text-3xl">
        ✓
      </div>
      <h2 className="text-xl font-semibold">{t("DoneTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("DoneBody")}</p>

      {/* ADR 044: this is the only time the code is ever shown. A household has
          no second admin to let anyone back in. */}
      {recoveryCode && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 p-4 text-left space-y-3">
          <h3 className="text-sm font-semibold">{t("RecoveryTitle")}</h3>
          <p className="text-xs text-muted-foreground">{t("RecoveryBody")}</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-background px-3 py-2 font-mono text-sm tracking-widest select-all">
              {recoveryCode}
            </code>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(recoveryCode).then(() => setCopied(true)).catch(() => {});
              }}
              className="rounded-lg border px-3 py-2 text-xs font-medium hover:bg-accent"
            >
              {copied ? t("Copied") : t("Copy")}
            </button>
          </div>
          <label className="flex items-start gap-2 text-xs">
            <input
              type="checkbox"
              checked={noted}
              onChange={(e) => setNoted(e.target.checked)}
              className="mt-0.5"
            />
            <span>{t("RecoveryConfirm")}</span>
          </label>
        </div>
      )}

      <button
        type="button"
        onClick={goToLogin}
        disabled={Boolean(recoveryCode) && !noted}
        className="mt-2 px-6 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {t("GoToLogin")}
      </button>
    </div>
  );
}
