import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getPatient, getOpenShareRequests, getPatientShares, getDocuments, getShareLinks, getDataSetRows } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AccessPanel } from "../AccessPanel";
import { SharingConsentPanel } from "../SharingConsentPanel";
import { ShareLinksPanel } from "../ShareLinksPanel";
import { ErasePatientButton } from "../ErasePatientButton";
import type { S } from "@/lib/api";
import { backendFetch } from "@/lib/backend";

async function getCaregivers(patientId: string, accessToken: string): Promise<{ caregivers: S<"CaregiverDto">[]; canManage: boolean }> {
  const res = await backendFetch(`/api/patients/${patientId}/access`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (!res.ok) return { caregivers: [], canManage: false };
  return { caregivers: await res.json(), canManage: true };
}

// Management lives on its own page, off the clinical overview (tester feedback):
// access & caregivers, data sharing, share links, and the danger zone.
export default async function PatientManagePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, session, t] = await Promise.all([
    getPatient(id).catch(() => null),
    auth(),
    getTranslations("Patient"),
  ]);
  if (!patient) notFound();

  const accessToken = session?.accessToken as string | undefined;
  const currentUserEmail = session?.user?.email as string | undefined;
  const { caregivers, canManage } = accessToken
    ? await getCaregivers(id, accessToken).catch(() => ({ caregivers: [], canManage: false }))
    : { caregivers: [], canManage: false };

  const [openRequests, patientShares, documents, shareLinks] = await Promise.all([
    getOpenShareRequests(id).catch(() => []),
    getPatientShares(id).catch(() => []),
    getDocuments(id).catch(() => []),
    getShareLinks(id).catch(() => []),
  ]);

  // ADR 064: the rows a Data Set request or "share again" would send
  const dataSetPurposes = [
    ...openRequests.filter((r) => r.data_set).map((r) => r.id),
    ...patientShares.filter((s) => s.data_set && s.status === "active" && s.purpose_open).map((s) => s.sharing_purpose_id),
  ];
  const rowsByPurpose = Object.fromEntries(
    await Promise.all(dataSetPurposes.map(async (pid) => [pid, await getDataSetRows(id, pid).catch(() => [])] as const)),
  );

  const isAdmin = caregivers.some((c) => c.user_email === currentUserEmail && c.access_level === "admin");

  return (
    <AppLayout>
      <div className="mb-6">
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Manage")}
          className=""
        />
      </div>

      {canManage && (
        <div className="mb-6">
          <AccessPanel patientId={id} caregivers={caregivers} currentUserEmail={currentUserEmail} />
        </div>
      )}

      <div className="mb-6">
        <SharingConsentPanel patientId={id} openRequests={openRequests} shares={patientShares} documents={documents} rowsByPurpose={rowsByPurpose} />
      </div>

      {shareLinks.length > 0 && (
        <div className="mb-6">
          <ShareLinksPanel patientId={id} links={shareLinks} documents={documents} />
        </div>
      )}

      {/* ADR 052: everyone who can see the Patient can take it with them */}
      <div className="mb-6 rounded-xl border bg-card p-4">
        <h2 className="text-sm font-semibold mb-1">{t("ExportTitle")}</h2>
        <p className="text-xs text-muted-foreground mb-3">{t("ExportHint")}</p>
        <a href={`/api/patients/${id}/export`} download className="inline-block rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted">
          {t("ExportButton")}
        </a>
      </div>

      {isAdmin && (
        <div className="mt-8 rounded-xl border border-red-200 dark:border-red-900 p-4">
          <h2 className="text-sm font-semibold text-destructive mb-1">{t("DangerZone")}</h2>
          <p className="text-xs text-muted-foreground mb-3">{t("EraseWarning")}</p>
          <ErasePatientButton patientId={id} patientName={`${patient.given_name} ${patient.family_name}`} />
        </div>
      )}
    </AppLayout>
  );
}
