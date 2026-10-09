import { AppLayout } from "@/components/layout/AppLayout";
import { getHistoryFacts, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { HistoryFactsView } from "./HistoryFactsView";

export default async function HistoryFactsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("HistoryFacts");
  const ti = await getTranslations("IntakeForms");
  const [patient, facts] = await Promise.all([getPatient(id).catch(() => null), getHistoryFacts(id).catch(() => null)]);

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{ti("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="mb-4">
        <Breadcrumb
          crumbs={[
            { label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` },
            { label: ti("Title"), href: `/patients/${id}/intake-forms` },
          ]}
          current={t("Title")}
          className=""
        />
      </div>
      <p className="mb-6 text-sm text-muted-foreground">{t("Intro")}</p>
      {facts === null ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {ti("LoadError")}
        </div>
      ) : (
        <HistoryFactsView patientId={id} facts={facts} />
      )}
    </AppLayout>
  );
}
