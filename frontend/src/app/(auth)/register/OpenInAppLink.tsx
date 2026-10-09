"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/** Deep link into the mobile shell (ADR 023): shown only in mobile browsers,
 *  hidden when already running inside the shell (Capacitor bridge present). */
export function OpenInAppLink({ token }: { token: string }) {
  const t = useTranslations("Auth");
  const [href, setHref] = useState<string | null>(null);

  useEffect(() => {
    if ((window as { Capacitor?: unknown }).Capacitor) return;
    if (!/Android|iPhone|iPad/i.test(navigator.userAgent)) return;
    const params = new URLSearchParams({ url: window.location.origin, token });
    setHref(`openavisio://connect?${params}`);
  }, [token]);

  if (!href) return null;
  return (
    <a href={href} className="block text-center text-sm text-muted-foreground underline underline-offset-4">
      {t("OpenInApp")}
    </a>
  );
}
