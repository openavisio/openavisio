import { AppLayout } from "@/components/layout/AppLayout";
import { getConditions, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AiNotice } from "@/components/AiNotice";
import { ConditionsTable } from "./ConditionsTable";

export default async function ConditionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Conditions");
  let patient: any = null;
  let conditions: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { conditions = await getConditions(id); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("patientNotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("title")}
      />

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("loadError")}
        </div>
      ) : conditions.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("empty")}</div>
      ) : (
        <ConditionsTable conditions={conditions} patientId={id} />
      )}
      {conditions.length > 0 && <AiNotice />}

    </AppLayout>
  );
}
