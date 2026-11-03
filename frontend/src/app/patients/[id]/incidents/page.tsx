import { AppLayout } from "@/components/layout/AppLayout";
import { getEmergencyPlan, getIncidentDoses, getIncidents, getMedications, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { IncidentsView } from "./IncidentsView";

export default async function IncidentsPage({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ open?: string }>;
}) {
  const { id } = await params;
  const { open } = await searchParams;
  const t = await getTranslations("Incidents");
  let patient: Awaited<ReturnType<typeof getPatient>> | null = null;
  let incidents: Awaited<ReturnType<typeof getIncidents>> = [];
  let medications: Awaited<ReturnType<typeof getMedications>> = [];
  let doses: Awaited<ReturnType<typeof getIncidentDoses>> = [];
  let rescue: string[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { incidents = await getIncidents(id); } catch { fetchError = true; }
  try { medications = await getMedications(id); } catch {}
  try { doses = await getIncidentDoses(id); } catch {}
  // ADR 060: the Emergency Plan's medications come first when a Dose is given with an Incident
  try {
    const plan = await getEmergencyPlan(id);
    rescue = (plan?.situations ?? []).flatMap((s) => s.steps.map((st) => st.medication_id).filter((m): m is string => !!m));
  } catch {}

  if (!patient) {
    return <AppLayout><div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div></AppLayout>;
  }

  return (
    <AppLayout>
      <Breadcrumb crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]} current={t("Title")} />
      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />{t("LoadError")}
        </div>
      ) : (
        <IncidentsView key={open ?? ""} patientId={id} incidents={incidents} medications={medications} doses={doses} rescue={rescue} openId={open} />
      )}
    </AppLayout>
  );
}
