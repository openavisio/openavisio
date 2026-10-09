import { AppLayout } from "@/components/layout/AppLayout";
import { getEinstufungen, getEinstufungScale, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AddEinstufungPanel } from "./AddEinstufungPanel";
import { EinstufungView } from "./EinstufungView";
import { AiNotice } from "@/components/AiNotice";

export default async function EinstufungPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Einstufung");
  // one round trip, like the expenses page: serialising these pushed first paint
  const [patient, data] = await Promise.all([
    getPatient(id).catch(() => null),
    Promise.all([getEinstufungen(id), getEinstufungScale(id)]).catch(() => null),
  ]);
  const fetchError = data === null;
  const [rows, scale] = data ?? [[], null];

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AddEinstufungPanel patientId={id}>
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Title")}
          className=""
        />
      </AddEinstufungPanel>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : rows.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <EinstufungView rows={rows} scale={scale} />
      )}
      {rows.length > 0 && <AiNotice />}
    </AppLayout>
  );
}
