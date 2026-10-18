import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { ThemeProvider } from "next-themes";
import { ThemeColorMeta } from "@/components/providers/ThemeColorMeta";
import { HighContrastProvider } from "@/components/providers/HighContrastProvider";
import { UmamiNotice } from "@/components/UmamiNotice";
import localFont from "next/font/local";
import "./globals.css";

// House typeface (business/corporate-design): Atkinson Hyperlegible Next, built for
// legibility — l, I and 1 stay apart. Served from our own origin, no font CDN.
const atkinson = localFont({
  src: [
    { path: "./fonts/atkinson-hyperlegible-next-latin-wght-normal.woff2", weight: "200 800", style: "normal" },
    { path: "./fonts/atkinson-hyperlegible-next-latin-wght-italic.woff2", weight: "200 800", style: "italic" },
  ],
  variable: "--font-atkinson",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OpenAvisio",
  description: "The AI assistant for everyone who cares",
  // Safari ignores the manifest's icons — without appleWebApp iOS uses a
  // screenshot of the page as the home-screen icon. app/apple-icon.png supplies
  // the image; `capable` makes the launched app full-screen instead of a tab.
  appleWebApp: {
    capable: true,
    title: "OpenAvisio",
    statusBarStyle: "default",
  },
};

// viewport-fit=cover so content can use the safe-area insets (notch, home indicator) (#80)
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // No themeColor here on purpose. It would be keyed on prefers-color-scheme —
  // the SYSTEM setting — while the app has its own theme switch, so a dark app on
  // a light phone got bright bars. ThemeColorMeta owns the tag instead, and owns
  // it ALONE: it used to delete React's tags, which pulled nodes out from under
  // React and crashed the renderer mid-navigation ("Cannot read properties of
  // null (reading 'removeChild')") — the URL changed and the page did not.
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  const t = await getTranslations("Preview");

  // "Not ready for production use" shipped to production unconditionally (#110).
  // Either it is true — then do not onboard patients — or it is stale and must go.
  // The instance decides: set PREVIEW_BANNER=true on the test servers.
  const previewBanner = process.env.PREVIEW_BANNER === "true";
  // the public demo refuses every write but the sample and the chat (backend app/demo.py)
  const demoBanner = process.env.DEMO_MODE === "true";

  // Opt-in, per instance: self-hosted, cookieless Umami. Unset (the default)
  // means no analytics at all — that is the product's promise; only our own
  // demo/website instances set these.
  const umamiUrl = process.env.UMAMI_URL;
  const umamiId = process.env.UMAMI_WEBSITE_ID;

  return (
    <html lang={locale} suppressHydrationWarning className={`h-full ${atkinson.variable}`}>
      {/* ADR 053: the error page offers a report to the operator; only a hosted Deployment has one to name */}
      <body className="h-full bg-background text-foreground antialiased"
        data-support={process.env.HOSTED_SETUP === "true" ? "info@openavisio.app" : undefined}>
        {umamiUrl && umamiId && (
          <script defer src={`${umamiUrl}/script.js`} data-website-id={umamiId} />
        )}
        {previewBanner && (
        <div className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200 text-center text-xs py-1.5 px-4 font-medium pt-[max(0.375rem,env(safe-area-inset-top))]">
          {t("banner")}
        </div>
        )}
        {demoBanner && (
        <div className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200 text-center text-xs py-1.5 px-4 font-medium pt-[max(0.375rem,env(safe-area-inset-top))]">
          {t("demo")}
        </div>
        )}
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {/* the status bar follows the APP theme, not the system one */}
          <ThemeColorMeta />
          <HighContrastProvider>
            <NextIntlClientProvider messages={messages}>
              {children}
              {umamiUrl && umamiId && <UmamiNotice />}
            </NextIntlClientProvider>
          </HighContrastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
