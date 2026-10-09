import { AppLayout } from "@/components/layout/AppLayout";
import { getPatient } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getTranslations } from "next-intl/server";
import { CalendarGrid } from "./CalendarGrid";
import { CalendarFeedPanel } from "./CalendarFeedPanel";

export default async function CalendarPage({
  params, searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ month?: string }>;
}) {
  const { id } = await params;
  const { month } = await searchParams;
  const tp = await getTranslations("Patient");
  let patient: any = null;
  try { patient = await getPatient(id); } catch {}

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={patient ? [{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }] : []}
        current={tp("Calendar")}
      />
      <CalendarGrid patientId={id} birthDate={patient?.birth_date} initialMonth={month} />
      <div className="mt-6">
        <CalendarFeedPanel patientId={id} />
      </div>
    </AppLayout>
  );
}
