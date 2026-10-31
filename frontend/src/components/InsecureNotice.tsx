"use client";

import { useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";

const never = () => () => {};

/** Plain http: data travels in the clear and the browser withholds passkeys. Say so at the top. */
export function InsecureNotice() {
  const t = useTranslations("Preview");
  // the server cannot know: render nothing there, the client decides
  const secure = useSyncExternalStore(never, () => window.isSecureContext, () => true);
  if (secure) return null;
  return (
    <div role="alert" className="w-full bg-red-50 border-b border-red-200 text-red-900 dark:bg-red-950 dark:border-red-800 dark:text-red-200 text-center text-xs py-1.5 px-4 font-medium pt-[max(0.375rem,env(safe-area-inset-top))]">
      {t("insecure")}
    </div>
  );
}
