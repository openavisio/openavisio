"use client";

import { useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";

// ADR 053: the number is Next's digest; the frontend log has it next to the backend's error id.
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useTranslations("ErrorPage");
  const support = useSyncExternalStore(() => () => {}, () => document.body.dataset.support, () => undefined);
  const id = error.digest ?? "-";
  const mail = support && `mailto:${support}?subject=${encodeURIComponent(t("MailSubject", { id }))}` +
    `&body=${encodeURIComponent(t("MailBody", { id, page: typeof window === "undefined" ? "" : window.location.pathname }))}`;

  return (
    <div className="mx-auto max-w-md px-4 py-16 space-y-4 text-center">
      <h1 className="text-xl font-semibold">{t("Title")}</h1>
      <p className="text-sm text-muted-foreground">{t("Body")}</p>
      <p className="text-xs text-muted-foreground">{t("Number")} <code className="font-mono">{id}</code></p>
      <div className="flex justify-center gap-3 flex-wrap">
        <button onClick={reset} className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted">{t("Retry")}</button>
        {mail && (
          <a href={mail} className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90">
            {t("Report")}
          </a>
        )}
      </div>
    </div>
  );
}
