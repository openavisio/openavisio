import { cookies } from "next/headers"
import { auth } from "@/auth"
import { getOrganization, getGroups, getFavoritePatients } from "@/lib/api"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "./AppSidebar"
import { MobileTabBar } from "./MobileTabBar"
import { PatientSectionSwitcher } from "./PatientSectionSwitcher"
import { PatientMiniHeader } from "./PatientMiniHeader"
import { AppFooter } from "./AppFooter"

export async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  let orgName = "OpenAvisio"
  // ADR 046: a household hides the organisation machinery it will never use.
  let isHousehold = false
  try {
    const org = await getOrganization()
    orgName = org?.name ?? orgName
    isHousehold = org?.is_household ?? false
  } catch {}

  const user = session?.user as any

  let hasGroups = false
  try { hasGroups = (await getGroups()).length > 0 } catch {}

  let favorites: { id: string; given_name: string; family_name: string }[] = []
  try { favorites = await getFavoritePatients() } catch {}

  // SidebarProvider writes the collapsed state to a cookie but never read it
  // back, so every navigation re-rendered the sidebar expanded.
  const sidebarOpen = (await cookies()).get("sidebar_state")?.value !== "false"

  return (
    <SidebarProvider defaultOpen={sidebarOpen}>
      <AppSidebar orgName={orgName} userRole={user?.role} userName={user?.name} hasGroups={hasGroups} isHousehold={isHousehold} favorites={favorites} />
      <SidebarInset>
        {/* No chrome header — the collapse toggle now lives in the sidebar
            itself, and on mobile the bottom nav is the sole navigation (ADR 030) */}
        {/* flex column so the footer sits on the bottom edge of short pages
            instead of floating right underneath the content */}
        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          <div className="flex-1 p-4 sm:p-6 lg:px-8 pb-[calc(5rem+env(safe-area-inset-bottom))] lg:pb-6">
            {/* wide, but capped - full width ran away on wide monitors (#80) */}
            <div className="mx-auto max-w-[1200px] space-y-6">
              <PatientMiniHeader />
              <PatientSectionSwitcher />
              {children}
            </div>
          </div>

          <AppFooter orgName={orgName} />
        </div>
      </SidebarInset>
      <MobileTabBar userRole={user?.role} userName={user?.name} hasGroups={hasGroups} isHousehold={isHousehold} favorites={favorites} />
    </SidebarProvider>
  )
}
