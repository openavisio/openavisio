"use client"

import {
  Home,
  Users,
  UsersRound,
  Shield,
  LogOut,
  Sun,
  Moon,
  Contrast,
  Settings,
  UserCog,
  Building2,
  UserPlus,
  ClipboardList,
  ScrollText,
  Bot,
  BadgeCheck,
  MonitorDot,
  Building,
  Share2,
  Star,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react"
import Image from "next/image"
import { usePathname } from "next/navigation"
import Link from "next/link"
import { Fragment, useEffect, useState } from "react"
import { PATIENT_SECTIONS } from "@/lib/patientSections"
import { getPatient } from "@/lib/api"
import { useTheme } from "next-themes"
import { useHighContrast } from "@/components/providers/HighContrastProvider"
import { signOut } from "next-auth/react"
import { useTranslations } from "next-intl"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

// The section tint carries bg + text; the nav only wants the text colour.
const textTint = (tint: string) => tint.split(" ").filter((c) => c.includes("text-")).join(" ")

interface AppSidebarProps {
  orgName: string
  userRole?: string
  userName?: string
  hasGroups?: boolean
  isHousehold?: boolean
  hosted?: boolean
  favorites?: { id: string; given_name: string; family_name: string }[]
}

export function AppSidebar({ orgName, userRole, userName, hasGroups, isHousehold, hosted, favorites = [] }: AppSidebarProps) {
  const t = useTranslations("Nav")
  const tp = useTranslations("Patient")
  const pathname = usePathname()
  const { state, toggleSidebar } = useSidebar()
  const collapsed = state === "collapsed"
  const { resolvedTheme, setTheme } = useTheme()
  const { highContrast, toggle: toggleHighContrast } = useHighContrast()

  // Contextual patient nav (#77): while inside /patients/[id]/… show that
  // patient's sections above the global nav. Name is fetched client-side.
  const patientMatch = pathname.match(/^\/patients\/([^/]+)(?:\/|$)/)
  const patientId = patientMatch && patientMatch[1] !== "new" ? patientMatch[1] : null
  const [patientName, setPatientName] = useState<string | null>(null)
  useEffect(() => {
    if (!patientId) { setPatientName(null); return }
    let active = true
    getPatient(patientId)
      .then((p) => { if (active) setPatientName(`${p.given_name} ${p.family_name}`) })
      .catch(() => {})
    return () => { active = false }
  }, [patientId])

  // ADR 046: in a household there are no Groups, no Sharing Purposes and no
  // user management. Invitations stay — that is how the other parent gets in.
  const canShare = (userRole === "admin" || userRole === "manager") && !isHousehold && !hosted
  const showGroups = (canShare || hasGroups) && !isHousehold
  // Azure-DevOps-style: coloured top-level groups, grey contextual sub-nav (#77).
  const navMain = [
    { href: "/", label: t("Home"), icon: Home, color: "text-teal-600 dark:text-teal-400" },
    { href: "/patients", label: t("Patients"), icon: Users, color: "text-amber-600 dark:text-amber-400" },
    ...(showGroups ? [{ href: "/group", label: t("Group"), icon: UsersRound, color: "text-sky-600 dark:text-sky-400" }] : []),
    ...(canShare ? [{ href: "/admin/sharing", label: t("DataSharing"), icon: Share2, color: "text-emerald-600 dark:text-emerald-400" }] : []),
    { href: "/settings", label: t("Settings"), icon: Settings, color: "text-slate-500 dark:text-slate-400" },
  ]

  const allAdminItems = [
    { href: "/admin/system", label: t("System"), icon: MonitorDot, color: "text-cyan-600 dark:text-cyan-400" },
    { href: "/admin/organization", label: t("Organization"), icon: Building, color: "text-indigo-600 dark:text-indigo-400" },
    ...(isHousehold ? [] : [
      { href: "/admin/users", label: t("Users"), icon: UserCog, color: "text-amber-600 dark:text-amber-400" },
      { href: "/admin/groups", label: t("Groups"), icon: Building2, color: "text-sky-600 dark:text-sky-400" },
    ]),
    { href: "/admin/invitations", label: t("Invitations"), icon: UserPlus, color: "text-emerald-600 dark:text-emerald-400" },
    { href: "/admin/audit", label: t("AuditLog"), icon: ClipboardList, color: "text-violet-600 dark:text-violet-400" },
    { href: "/admin/logs", label: t("Logs"), icon: ScrollText, color: "text-slate-500 dark:text-slate-400" },
    { href: "/admin/ollama", label: t("Ollama"), icon: Bot, color: "text-fuchsia-600 dark:text-fuchsia-400" },
    { href: "/admin/license", label: t("License"), icon: BadgeCheck, color: "text-lime-600 dark:text-lime-400" },
    { href: "/admin/data-governance", label: t("DataGovernance"), icon: Shield, color: "text-rose-600 dark:text-rose-400" },
  ]

  const adminItems = hosted ? allAdminItems.filter((i) => ["/admin/invitations", "/admin/audit"].includes(i.href)) : allAdminItems

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href)

  return (
    <Sidebar collapsible="icon">
      {/* Brand header. The signet is square; collapsed, bound it by width so it
          fits the 3rem rail. */}
      <SidebarHeader>
        <div className="flex items-center gap-3 px-2 py-1.5 group-data-[collapsible=icon]/sidebar:px-0 group-data-[collapsible=icon]/sidebar:justify-center">
          <Image
            src="/logo.png"
            alt="OpenAvisio"
            width={32}
            height={32}
            className="h-8 w-auto shrink-0 group-data-[collapsible=icon]/sidebar:h-auto group-data-[collapsible=icon]/sidebar:w-9"
          />
          <div className="grid flex-1 leading-tight group-data-[collapsible=icon]/sidebar:hidden">
            <span className="truncate text-sm font-semibold">{orgName}</span>
            <span className="truncate text-xs text-sidebar-foreground/60">Health Portal</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {/* Main nav */}
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navMain.map((item) => (
                <Fragment key={item.href}>
                  {/* Settings is housekeeping, not a place you work — set it apart.
                      In an <li>: a <ul> may only contain <li>, and a bare <div> made
                      the browser hoist it out of the list. The DOM then differed from
                      the server HTML — hydration failed (React #418), the client
                      router died, and only every second click navigated. */}
                  {item.href === "/settings" && (
                    <li aria-hidden className="py-1">
                      <SidebarSeparator />
                    </li>
                  )}

                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={isActive(item.href)} tooltip={item.label}>
                      <Link href={item.href}>
                        <item.icon className={item.color} />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Collapsed to icons there is no room for a nested tree, so
                      the sections become icon rows. The stripe belongs to the
                      group, not to each button — per-button borders break
                      wherever the menu's row gap falls. */}
                  {item.href === "/patients" && patientId && collapsed && (
                    <li>
                      <ul className="flex flex-col gap-1 border-l-2 border-sidebar-border pl-0.5">
                        {PATIENT_SECTIONS.map(({ key, segment, Icon, tint }) => {
                          const href = `/patients/${patientId}/${segment}`
                          return (
                            <SidebarMenuItem key={segment}>
                              <SidebarMenuButton asChild isActive={pathname.startsWith(href)} tooltip={tp(key)}>
                                <Link href={href}>
                                  <Icon className={textTint(tint)} />
                                  <span>{tp(key)}</span>
                                </Link>
                              </SidebarMenuButton>
                            </SidebarMenuItem>
                          )
                        })}
                      </ul>
                    </li>
                  )}

                  {/* Contextual patient sections, nested under Patients (#77).
                      In an <li>: SidebarMenuSub is a <ul>, and a <ul> may not be a
                      direct child of another <ul> — the browser hoists it out, the
                      DOM stops matching the server HTML, hydration fails (React
                      #418) and the client router never takes over. That is why only
                      every second click navigated, and why it happened on patient
                      pages: this subtree only renders there. */}
                  {item.href === "/patients" && patientId && !collapsed && (
                    <li>
                    <SidebarMenuSub>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={pathname === `/patients/${patientId}`}>
                          <Link href={`/patients/${patientId}`}>
                            <span className="truncate font-medium">{patientName ?? tp("Details")}</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                      {PATIENT_SECTIONS.map(({ key, segment, Icon, tint }) => {
                        const href = `/patients/${patientId}/${segment}`
                        return (
                          <SidebarMenuSubItem key={segment}>
                            <SidebarMenuSubButton asChild isActive={pathname.startsWith(href)}>
                              <Link href={href}>
                                <Icon className={textTint(tint)} />
                                <span>{tp(key)}</span>
                              </Link>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        )
                      })}
                    </SidebarMenuSub>
                    </li>
                  )}
                </Fragment>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {favorites.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel>
              <Star className="mr-1.5 size-3 text-amber-500" fill="currentColor" />
              {t("Favorites")}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {favorites.map((p) => (
                  <SidebarMenuItem key={p.id}>
                    <SidebarMenuButton asChild isActive={isActive(`/patients/${p.id}`)} tooltip={`${p.given_name} ${p.family_name}`}>
                      <Link href={`/patients/${p.id}`}>
                        <Star className="text-amber-500" fill="currentColor" />
                        <span>{p.given_name} {p.family_name}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {/* Admin section */}
        {userRole === "admin" && (
          <>
            <SidebarSeparator />
            <SidebarGroup>
              <SidebarGroupLabel>
                <Shield className="mr-1.5 size-3" />
                {t("Admin")}
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {adminItems.map((item) => (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton asChild isActive={isActive(item.href)} tooltip={item.label}>
                        <Link href={item.href}>
                          <item.icon className={item.color} />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>

      {/* Footer */}
      <SidebarFooter>
        <SidebarSeparator />
        <SidebarMenu>
          {/* Azure-DevOps style: collapse sits at the bottom of the bar, as the
              last menu row — not floating in the content area beside it. */}
          <SidebarMenuItem>
            <SidebarMenuButton onClick={toggleSidebar} tooltip={t("Expand")}>
              {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
              <span>{t("Collapse")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
              {resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
              <span>{resolvedTheme === "dark" ? "Light mode" : "Dark mode"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={toggleHighContrast}>
              <Contrast className="size-4" />
              <span>{highContrast ? "Standard contrast" : "High contrast"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => signOut({ callbackUrl: "/login" })}
            >
              <LogOut className="size-4" />
              <span>{t("Logout")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {userName && (
          <div className="flex items-center gap-2 px-2 pb-1 group-data-[collapsible=icon]/sidebar:justify-center">
            <Avatar className="size-7 shrink-0">
              <AvatarFallback className="text-xs bg-sidebar-accent text-sidebar-accent-foreground">
                {userName.charAt(0).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="truncate text-xs text-sidebar-foreground/70 group-data-[collapsible=icon]/sidebar:hidden">{userName}</span>
          </div>
        )}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
