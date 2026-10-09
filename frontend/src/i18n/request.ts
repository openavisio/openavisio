import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";
import { routing } from "./routing";

const API = process.env.API_URL || "http://localhost:8000";

// Resolve the best supported locale from the Accept-Language header.
// Used for anonymous visitors (e.g. external share links) who have no locale cookie.
async function getBrowserLanguage(): Promise<string | null> {
  try {
    const accept = (await headers()).get("accept-language");
    if (!accept) return null;
    for (const part of accept.split(",")) {
      const tag = part.split(";")[0].trim().toLowerCase();
      const primary = tag.split("-")[0];
      if (routing.locales.includes(primary as any)) return primary;
    }
  } catch {}
  return null;
}

async function getOrgDefaultLanguage(): Promise<string> {
  try {
    const res = await fetch(`${API}/api/organization/status`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const data = await res.json();
      const lang = data.default_language as string | undefined;
      if (lang && routing.locales.includes(lang as any)) return lang;
    }
  } catch {}
  return routing.defaultLocale;
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;

  const locale =
    (cookieLocale && routing.locales.includes(cookieLocale as any) ? cookieLocale : null) ??
    (await getBrowserLanguage()) ??
    (await getOrgDefaultLanguage());

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
