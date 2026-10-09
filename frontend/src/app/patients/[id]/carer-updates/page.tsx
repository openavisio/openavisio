import { AppLayout } from "@/components/layout/AppLayout";
import { getCarerUpdates, getCorrespondents, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { CarerUpdatesView } from "./CarerUpdatesView";

export default async function CarerUpdatesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("CarerUpdates");
  const [patient, updates, correspondents] = await Promise.all([
    getPatient(id).catch(() => null),
    getCarerUpdates(id).catch(() => null),
    getCorrespondents().catch(() => []),
  ]);

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  const crumb = (
    <Breadcrumb
      crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
      current={t("Title")}
      className=""
    />
  );

  return (
    <AppLayout>
      {updates === null ? (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {t("LoadError")}
          </div>
        </>
      ) : (
        <CarerUpdatesView patientId={id} updates={updates} correspondents={correspondents}>{crumb}</CarerUpdatesView>
      )}
    </AppLayout>
  );
}
