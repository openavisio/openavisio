"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

const ACK = "oa-privacy-acknowledged";
const DISABLED = "umami.disabled";

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}

// the server has no localStorage: render as if acknowledged, the client corrects it
function useStored(key: string, onServer: string | null) {
  return useSyncExternalStore(subscribe, () => localStorage.getItem(key), () => onServer);
}

function store(...keys: string[]) {
  for (const k of keys) localStorage.setItem(k, "1");
  window.dispatchEvent(new StorageEvent("storage"));  // same-tab writes fire no event
}

// Umami's script skips tracking while umami.disabled is set (objection, Art. 21 DSGVO)
const object = () => store(DISABLED, ACK);

/** Only rendered where UMAMI_URL is set, i.e. on the project's own instances. */
export function UmamiNotice() {
  const t = useTranslations("Umami");
  if (useStored(ACK, "1")) return null;
  return (
    <div
      role="region"
      aria-label={t("label")}
      className="fixed inset-x-0 bottom-0 z-[60] flex flex-wrap items-center justify-center gap-3 border-t bg-card px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] text-sm text-muted-foreground shadow-lg"
    >
      <p>
        {t("text")}{" "}
        <Link href="/privacy" className="underline underline-offset-2">{t("privacy")}</Link>
      </p>
      <Button size="sm" onClick={() => store(ACK)}>OK</Button>
      <Button size="sm" variant="outline" onClick={object}>{t("object")}</Button>
    </div>
  );
}

export function UmamiOptOut() {
  const t = useTranslations("Umami");
  if (useStored(DISABLED, null)) return <span role="status">{t("optOutDone")}</span>;
  return (
    <button type="button" className="underline underline-offset-2" onClick={object}>
      {t("optOut")}
    </button>
  );
}
