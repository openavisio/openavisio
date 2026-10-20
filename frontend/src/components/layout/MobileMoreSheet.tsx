"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Home, Users, UsersRound, Share2, Settings, Star, Shield, Menu,
  Sun, Moon, Contrast, LogOut, MonitorDot, Building, UserCog, Building2,
  UserPlus, ClipboardList, ScrollText, Bot, BadgeCheck,
  HeartHandshake,
} from "lucide-react";
import { useTheme } from "next-themes";
import { signOut } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useHighContrast } from "@/components/providers/HighContrastProvider";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

type Fav = { id: string; given_name: string; family_name: string };

// The mobile "More" tab — a bottom sheet holding everything that used to live in
// the left sidebar (global nav, admin, favourites, theme, logout). Replaces the
// left drawer on mobile (ADR 030).
export function MobileMoreSheet({
  userRole, userName, hasGroups, isHousehold, hosted, favorites = [], active, triggerClassName,
}: {
  userRole?: string;
  userName?: string;
  hasGroups?: boolean;
  isHousehold?: boolean;
  hosted?: boolean;
  favorites?: Fav[];
  active: boolean;
  triggerClassName?: string;
}) {
  const t = useTranslations("Nav");
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const { highContrast, toggle } = useHighContrast();
  const [open, setOpen] = useState(false);

  const canShare = (userRole === "admin" || userRole === "manager") && !isHousehold && !hosted;  // ADR 046
  const showGroups = (canShare || hasGroups) && !isHousehold;

  const nav = [
    { href: "/", label: t("Home"), Icon: Home },
    { href: "/patients", label: t("Patients"), Icon: Users },
    ...(isHousehold && userRole === "admin" ? [{ href: "/family", label: t("Family"), Icon: HeartHandshake }] : []),
    ...(showGroups ? [{ href: "/group", label: t("Group"), Icon: UsersRound }] : []),
    ...(canShare ? [{ href: "/admin/sharing", label: t("DataSharing"), Icon: Share2 }] : []),
    { href: "/settings", label: t("Settings"), Icon: Settings },
  ];
  const allAdminItems = userRole === "admin" ? [
    { href: "/admin/system", label: t("System"), Icon: MonitorDot },
    { href: "/admin/organization", label: t("Organization"), Icon: Building },
    ...(isHousehold ? [] : [
      { href: "/admin/users", label: t("Users"), Icon: UserCog },
      { href: "/admin/groups", label: t("Groups"), Icon: Building2 },
    ]),
    { href: "/admin/invitations", label: t("Invitations"), Icon: UserPlus },
    { href: "/admin/audit", label: t("AuditLog"), Icon: ClipboardList },
    { href: "/admin/logs", label: t("Logs"), Icon: ScrollText },
    { href: "/admin/ollama", label: t("Ollama"), Icon: Bot },
    { href: "/admin/license", label: t("License"), Icon: BadgeCheck },
    { href: "/admin/data-governance", label: t("DataGovernance"), Icon: Shield },
  ] : [];
  const familyPages = ["/admin/invitations", "/admin/audit"];  // ADR 052, as in AppSidebar
  const adminItems = isHousehold
    ? (hosted ? [] : allAdminItems.filter((i) => !familyPages.includes(i.href)))
    : hosted ? allAdminItems.filter((i) => familyPages.includes(i.href)) : allAdminItems;

  const row = "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-accent";

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        className={`${triggerClassName ?? "flex flex-1"} flex-col items-center justify-center gap-0.5 min-h-14 py-1.5 text-[11px] font-medium transition-colors ${
          active ? "text-primary" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <Menu className="size-6" />
        <span>{t("More")}</span>
      </SheetTrigger>
      <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-2xl pb-[env(safe-area-inset-bottom)]">
        <SheetTitle className="px-1 pb-2 text-base">{t("More")}</SheetTitle>

        <nav className="flex flex-col" onClick={() => setOpen(false)}>
          {nav.map(({ href, label, Icon }) => (
            <Link key={href} href={href} className={row}>
              <Icon className="size-5 text-muted-foreground" />
              <span>{label}</span>
            </Link>
          ))}

          {favorites.length > 0 && (
            <>
              <div className="mt-3 mb-1 flex items-center gap-1.5 px-3 text-xs font-medium text-muted-foreground">
                <Star className="size-3 text-amber-500" fill="currentColor" />
                {t("Favorites")}
              </div>
              {favorites.map((p) => (
                <Link key={p.id} href={`/patients/${p.id}`} className={row}>
                  <Star className="size-5 text-amber-500" />
                  <span>{p.given_name} {p.family_name}</span>
                </Link>
              ))}
            </>
          )}

          {adminItems.length > 0 && (
            <>
              <div className="mt-3 mb-1 flex items-center gap-1.5 px-3 text-xs font-medium text-muted-foreground">
                <Shield className="size-3" />
                {t(isHousehold ? "Server" : "Admin")}
              </div>
              {adminItems.map(({ href, label, Icon }) => (
                <Link key={href} href={href} className={row}>
                  <Icon className="size-5 text-muted-foreground" />
                  <span>{label}</span>
                </Link>
              ))}
            </>
          )}
        </nav>

        <div className="mt-3 border-t pt-2">
          <button type="button" className={`${row} w-full`} onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
            {resolvedTheme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
            <span>{resolvedTheme === "dark" ? t("LightMode") : t("DarkMode")}</span>
          </button>
          <button type="button" className={`${row} w-full`} onClick={toggle}>
            <Contrast className="size-5" />
            <span>{highContrast ? t("StandardContrast") : t("HighContrast")}</span>
          </button>
          <button
            type="button"
            className={`${row} w-full text-destructive hover:bg-destructive/10`}
            onClick={() => signOut({ callbackUrl: "/login" })}
          >
            <LogOut className="size-5" />
            <span>{t("Logout")}</span>
          </button>
          {userName && <div className="px-3 pt-1 text-xs text-muted-foreground">{userName}</div>}
        </div>
      </SheetContent>
    </Sheet>
  );
}
