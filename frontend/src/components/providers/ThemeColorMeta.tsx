"use client";

import { useEffect } from "react";
import { useTheme } from "next-themes";

// Must match the --background of each theme in globals.css
const COLORS = { light: "#f5f4ee", dark: "#262624" } as const;

/** Keep the browser chrome in step with the app's theme.
 *
 * `viewport.themeColor` is keyed on `prefers-color-scheme`, i.e. on the SYSTEM
 * setting. The app has its own switch. Turn the app dark on a light phone and
 * the status bar and the safe areas stayed cream — a bright band above and below
 * a dark app (#117 follow-up).
 */
export function ThemeColorMeta() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const color = COLORS[(resolvedTheme as keyof typeof COLORS) ?? "light"] ?? COLORS.light;

    // Our own tag, created once, updated in place. Never remove a node React
    // rendered — doing that crashes the renderer the next time it reconciles.
    let meta = document.head.querySelector<HTMLMetaElement>('meta[data-theme-color="app"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "theme-color");
      meta.setAttribute("data-theme-color", "app");
      document.head.appendChild(meta);
    }
    meta.content = color;
  }, [resolvedTheme]);

  return null;
}
