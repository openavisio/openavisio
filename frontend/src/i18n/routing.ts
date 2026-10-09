import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // de + en only for the D/A/CH launch; add more later by copying en.json
  locales: ["de", "en"],
  defaultLocale: "en",
  localePrefix: "never",
});
