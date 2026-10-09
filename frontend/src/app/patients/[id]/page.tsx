import { AppLayout } from "@/components/layout/AppLayout";
import { getPatient, getCalendarFeed, getCurrentEinstufung, getConditions } from "@/lib/api";
import Link from "next/link";
import { notFound } from "next/navigation";
import { formatDate } from "@/lib/utils";
import { getTranslations, getLocale } from "next-intl/server";
import { PATIENT_SECTIONS } from "@/lib/patientSections";
import { PatientPhotoEditor } from "@/components/PatientPhotoEditor";
import { UploadPanel } from "./documents/UploadPanel";
import { Cake, Venus, Mars, User as UserIcon, HeartHandshake, ChevronRight, CalendarDays, Settings, Upload, Printer, type LucideIcon } from "lucide-react";
import { Suspense } from "react";
import { CreatedBanner } from "./CreatedBanner";
import { FavoriteStar } from "@/components/FavoriteStar";

export default async function PatientDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t, td, locale] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Patient"),
    getTranslations("DocumentsPage"),
    getLocale(),
  ]);
  if (!patient) notFound();

  // next few upcoming items for the "today at a glance" agenda
  const today = new Date().toISOString().slice(0, 10);
  // The current Pflegegrad belongs where it is read off rather than looked up: it is
  // asked for on every form and every admission (ADR 042).
  const [feed, einstufung, conditions] = await Promise.all([
    getCalendarFeed(id, { from: today }).catch(() => [] as any[]),
    getCurrentEinstufung(id).catch(() => null),
    getConditions(id, "active").catch(() => []),
  ]);
  // #193
  const allergies = conditions
    .filter((c) => c.category === "allergy")
    .map((c) => (String(c.code_display).replace(/[-\s]*allerg(ie|y)$/i, "") || c.code_display) + (c.verification_status === "provisional" ? "?" : ""));
  // next few upcoming items for the "today at a glance" agenda
  const agenda = (feed as any[])
    .filter((i) => i.start)
    .sort((a, b) => String(a.start).localeCompare(String(b.start)))
    .slice(0, 3);


  return (
    <AppLayout>
      <Suspense>
        <CreatedBanner />
      </Suspense>
      {/* Patient header — warm, personal, not a data sheet (tester feedback) */}
      <div className="relative mb-6 overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/[0.06] via-card to-card p-5 sm:p-6">
        <HeartHandshake className="pointer-events-none absolute -right-6 -bottom-6 size-44 text-primary/[0.05]" strokeWidth={1} />
        <div className="relative flex items-start justify-between gap-3">
          <div className="flex items-center gap-4">
            <PatientPhotoEditor
              patientId={id}
              givenName={patient.given_name}
              familyName={patient.family_name}
              hasPhoto={!!patient.has_photo}
              labels={{ change: t("ChangePhoto"), remove: t("RemovePhoto"), failed: t("PhotoUploadFailed") }}
            />
            <div>
              <h1 className="text-2xl font-bold leading-tight sm:text-3xl">{patient.given_name} {patient.family_name}</h1>
              <span className={`mt-1.5 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${patient.active ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                <span className={`size-1.5 rounded-full ${patient.active ? "bg-emerald-500" : "bg-muted-foreground"}`} />
                {patient.active ? t("Active") : t("Inactive")}
              </span>
              {einstufung?.pflegegrad && (
                <a
                  href={`/patients/${id}/einstufung`}
                  className="mt-1.5 ml-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-500/20 dark:text-indigo-300"
                >
                  {t("PflegegradShort", { grade: einstufung.pflegegrad })}
                </a>
              )}
              {allergies.length > 0 && (
                <Link
                  href={`/patients/${id}/conditions`}
                  className="mt-1.5 ml-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-500/20 dark:text-indigo-300"
                >
                  {t("AllergiesShort", { names: allergies.slice(0, 2).join(", ") })}
                  {allergies.length > 2 && ` +${allergies.length - 2}`}
                </Link>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Link
              href={`/patients/${id}/handout`}
              className="mr-1 inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
            >
              <Printer className="size-4" />
              {t("Handout")}
            </Link>
            <FavoriteStar patientId={id} initial={!!patient.is_favorite} />
            <Link
              href={`/patients/${id}/manage`}
              title={t("Manage")}
              aria-label={t("Manage")}
              className="flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <Settings className="size-5" />
            </Link>
          </div>
        </div>
        <div className="relative mt-5 flex flex-wrap gap-x-8 gap-y-3 text-sm">
          {patient.birth_date && (
            <Meta Icon={Cake} label={t("Born")} value={formatDate(patient.birth_date, locale)} />
          )}
          {patient.gender && (
            <Meta
              Icon={patient.gender?.toLowerCase() === "female" ? Venus : patient.gender?.toLowerCase() === "male" ? Mars : UserIcon}
              label={t("Gender")}
              value={({ male: t("Male"), female: t("Female"), other: t("Other") } as Record<string, string>)[patient.gender?.toLowerCase()] ?? patient.gender}
            />
          )}
          {patient.identifier && (
            <Meta Icon={UserIcon} label={t("Identifier")} value={patient.identifier} />
          )}
        </div>
      </div>

      {/* Upload is the primary action — right on the overview, no detour to Documents (tester feedback) */}
      <div className="mb-6 rounded-2xl border bg-card p-4 sm:p-5">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Upload className="size-4 text-primary" />
          {td("uploadTitle")}
        </h2>
        <UploadPanel patientId={id} demoMode={process.env.DEMO_MODE === "true"} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {PATIENT_SECTIONS.map(({ key, segment, Icon, tint }) => (
          <Link
            key={segment}
            href={`/patients/${id}/${segment}`}
            className="group flex items-center gap-4 rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:shadow-md hover:border-primary/30"
          >
            <div className={`flex size-12 shrink-0 items-center justify-center rounded-xl ${tint}`}>
              <Icon className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-semibold">{t(key)}</div>
              <div className="truncate text-xs text-muted-foreground">{t(`desc.${key}`)}</div>
            </div>
            <ChevronRight className="size-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5" />
          </Link>
        ))}
      </div>

      {/* Today at a glance */}
      <div className="mt-6 rounded-2xl border bg-card p-5">
        <h2 className="mb-3 text-sm font-semibold">{t("TodayAtGlance")}</h2>
        {agenda.length === 0 ? (
          <p className="py-2 text-sm text-muted-foreground">{t("NothingUpcoming")}</p>
        ) : (
          <ul className="divide-y">
            {agenda.map((item) => (
              <li key={item.id}>
                <Link href={`/patients/${id}/calendar`} className="flex items-center gap-3 py-2.5 transition-colors hover:text-primary">
                  <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">{agendaWhen(item, today, locale, { today: t("Today"), tomorrow: t("Tomorrow") })}</span>
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: `${item.color}1a`, color: item.color }}>
                    <CalendarDays className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.title}</span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground/50" />
                </Link>
              </li>
            ))}
          </ul>
        )}
        <Link href={`/patients/${id}/calendar`} className="mt-2 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium text-primary hover:bg-primary/5">
          <CalendarDays className="size-4" />
          {t("ShowAllAppointments")}
        </Link>
      </div>
    </AppLayout>
  );
}

function Meta({ Icon, label, value }: { Icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      <div>
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className="font-medium">{value}</div>
      </div>
    </div>
  );
}

// "18:00" today, "Tomorrow", else a short date — the agenda's left-column label.
function agendaWhen(item: any, today: string, locale: string, labels: { today: string; tomorrow: string }): string {
  const date = String(item.start).slice(0, 10);
  const d = new Date(today + "T00:00:00");
  d.setDate(d.getDate() + 1);
  const tomorrow = d.toISOString().slice(0, 10);
  const time = !item.all_day && String(item.start).includes("T") ? String(item.start).slice(11, 16) : "";
  if (date === today) return time || labels.today;
  if (date === tomorrow) return labels.tomorrow;
  return formatDate(date, locale);
}
