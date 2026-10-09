"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { MobileMoreSheet } from "./MobileMoreSheet";

type Fav = { id: string; given_name: string; family_name: string };

// Native-style bottom nav (ADR 030) — the only mobile navigation, three stable
// tabs. Patient sections are handled by the in-page section switcher, not here,
// so the bar stays calm. The left sidebar is desktop-only.
export function MobileTabBar({
  userRole, userName, hasGroups, isHousehold, favorites = [],
}: {
  userRole?: string;
  userName?: string;
  hasGroups?: boolean;
  isHousehold?: boolean;
  favorites?: Fav[];
}) {
  const pathname = usePathname();
  const t = useTranslations("Nav");
  const moreActive = /^\/(admin|settings|group)/.test(pathname);

  const tab = (on: boolean) =>
    `flex flex-1 flex-col items-center justify-center gap-0.5 min-h-14 py-1.5 text-[11px] font-medium transition-colors ${
      on ? "text-primary" : "text-muted-foreground hover:text-foreground"
    }`;

  return (
    <nav className="lg:hidden fixed inset-x-0 bottom-0 z-40 border-t border-sidebar-border bg-sidebar/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
      <div className="flex items-stretch">
        <Link href="/" className={tab(pathname === "/")}>
          <Home className="size-6" />
          <span>{t("Home")}</span>
        </Link>
        <Link href="/patients" className={tab(pathname.startsWith("/patients"))}>
          <Users className="size-6" />
          <span>{t("Patients")}</span>
        </Link>
        <MobileMoreSheet userRole={userRole} userName={userName} hasGroups={hasGroups} isHousehold={isHousehold} favorites={favorites} active={moreActive} />
      </div>
    </nav>
  );
}
