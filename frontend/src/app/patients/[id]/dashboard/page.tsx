import { AppLayout } from "@/components/layout/AppLayout"
import { getDashboard, getPatient } from "@/lib/api"
import { Breadcrumb } from "@/components/Breadcrumb"
import { getTranslations } from "next-intl/server"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge, badgeVariants } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { VariantProps } from "class-variance-authority"

type BadgeVariant = VariantProps<typeof badgeVariants>["variant"]

function statusVariant(status: string): BadgeVariant {
  const map: Record<string, BadgeVariant> = {
    active: "success",
    completed: "info",
    verified: "success",
    resolved: "muted",
    stopped: "muted",
    failed: "destructive",
    pending: "warning",
    extracted: "secondary",
    revoked: "destructive",
  }
  return map[status?.toLowerCase()] ?? "muted"
}

export default async function DashboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const [patient, dashboard, tp] = await Promise.all([
    getPatient(id).catch(() => null),
    getDashboard(id).catch(() => null),
    getTranslations("Patient"),
  ])

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={patient ? [{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }] : []}
        current={tp("Dashboard")}
      />

      {!dashboard ? (
        <p className="text-sm text-muted-foreground">Failed to load dashboard data.</p>
      ) : (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Documents" value={dashboard.total_documents} />
            <StatCard label="Verified" value={dashboard.verified_documents} />
            <StatCard
              label="Active Conditions"
              value={dashboard.condition_timeline?.filter((c: any) => c.status === "active").length ?? 0}
            />
            <StatCard
              label="Active Medications"
              value={dashboard.medication_timeline?.filter((m: any) => m.status === "active").length ?? 0}
            />
          </div>

          {/* Conditions */}
          {dashboard.condition_timeline?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Condition Timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {dashboard.condition_timeline.map((c: any) => (
                  <div key={c.id} className="flex items-center justify-between gap-4 py-1">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{c.display}</p>
                      {c.onset && (
                        <p className="text-xs text-muted-foreground">
                          Onset {c.onset?.slice(0, 10)}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {c.severity && (
                        <Badge variant="outline" className="text-xs">{c.severity}</Badge>
                      )}
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Medications */}
          {dashboard.medication_timeline?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Medication Timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {dashboard.medication_timeline.map((m: any) => (
                  <div key={m.id} className="flex items-center justify-between gap-4 py-1">
                    <p className="text-sm font-medium truncate">{m.display}</p>
                    <Badge variant={statusVariant(m.status)} className="shrink-0">{m.status}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </AppLayout>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="pt-6 text-center">
        <p className="text-3xl font-bold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground mt-1">{label}</p>
      </CardContent>
    </Card>
  )
}
