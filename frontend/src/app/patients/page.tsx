import { AppLayout } from "@/components/layout/AppLayout"
import { auth } from "@/auth"
import { getPatients } from "@/lib/api"
import { getTranslations, getLocale } from "next-intl/server"
import { redirect } from "next/navigation"
import Link from "next/link"
import { formatDate } from "@/lib/utils"
import { UserPlus, User, AlertCircle, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { FavoriteStar } from "@/components/FavoriteStar"

export default async function PatientsPage() {
  let patients: any[] = []
  let fetchError = false
  const [session, t, locale] = await Promise.all([
    auth(),
    getTranslations("Patient"),
    getLocale(),
    getPatients().then((p) => { patients = p }).catch(() => { fetchError = true }),
  ])
  const role = (session?.user as any)?.role
  const canCreate = role === "admin" || role === "manager"
  // #70: a plain user with exactly one patient jumps straight in; staff (who can
  // create) keep the list to onboard more.
  if (!fetchError && !canCreate && patients.length === 1) {
    redirect(`/patients/${patients[0].id}`)
  }
  const genderLabel = (g: string) =>
    ({ male: t("Male"), female: t("Female"), other: t("Other") } as Record<string, string>)[g?.toLowerCase()] ?? g

  return (
    <AppLayout>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("Title")}</h1>
          {!fetchError && (
            <p className="text-sm text-muted-foreground mt-1">{t("Count", { count: patients.length })}</p>
          )}
        </div>
        {canCreate && (
          <Button asChild>
            <Link href="/patients/new">
              <UserPlus className="size-4" />
              {t("Create")}
            </Link>
          </Button>
        )}
      </div>

      {fetchError ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 py-16 text-center">
          <AlertCircle className="size-10 text-destructive/50 mb-3" />
          <p className="font-medium text-sm">{t("LoadErrorTitle")}</p>
          <p className="text-xs text-muted-foreground mt-1">{t("LoadErrorHint")}</p>
        </div>
      ) : patients.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
          <User className="size-10 text-muted-foreground/40 mb-3" />
          <p className="font-medium text-sm">{t("EmptyTitle")}</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
            {t("EmptyBody")}{" "}
            {canCreate ? t("EmptyActionCreate") : t("EmptyActionAsk")}
          </p>
        </div>
      ) : (
        (() => {
          const favorites = patients.filter((p: any) => p.is_favorite)
          const rest = patients.filter((p: any) => !p.is_favorite)
          const card = (p: any) => (
            <Link key={p.id} href={`/patients/${p.id}`} className="block group">
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
                        {(p.given_name?.[0] ?? "?").toUpperCase()}
                      </div>
                      <div>
                        <p className="font-semibold leading-tight">
                          {p.given_name} {p.family_name}
                        </p>
                        {p.identifier && (
                          <p className="text-xs text-muted-foreground mt-0.5">#{p.identifier}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant={p.active ? "success" : "muted"}>
                        {p.active ? t("Active") : t("Inactive")}
                      </Badge>
                      <FavoriteStar patientId={p.id} initial={!!p.is_favorite} />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    {p.birth_date && (
                      <>
                        <dt className="text-muted-foreground">{t("Born")}</dt>
                        <dd>{formatDate(p.birth_date, locale)}</dd>
                      </>
                    )}
                    {p.gender && (
                      <>
                        <dt className="text-muted-foreground">{t("Gender")}</dt>
                        <dd>{genderLabel(p.gender)}</dd>
                      </>
                    )}
                  </dl>
                </CardContent>
              </Card>
            </Link>
          )
          return (
            <div className="space-y-6">
              {favorites.length > 0 && (
                <section>
                  <h2 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground mb-3">
                    <Star className="size-4 text-amber-500" fill="currentColor" /> {t("Favorites")}
                  </h2>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{favorites.map(card)}</div>
                </section>
              )}
              <section>
                {favorites.length > 0 && (
                  <h2 className="text-sm font-medium text-muted-foreground mb-3">{t("AllPatients")}</h2>
                )}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{rest.map(card)}</div>
              </section>
            </div>
          )
        })()
      )}
    </AppLayout>
  )
}
