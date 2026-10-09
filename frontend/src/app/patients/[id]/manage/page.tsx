import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getPatient, getOpenShareRequests, getPatientShares, getDocuments, getShareLinks } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AccessPanel } from "../AccessPanel";
import { SharingConsentPanel } from "../SharingConsentPanel";
import { ShareLinksPanel } from "../ShareLinksPanel";
import { ErasePatientButton } from "../ErasePatientButton";

const API = process.env.API_URL || "http://localhost:8000";

async function getCaregivers(patientId: string, accessToken: string): Promise<{ caregivers: any[]; canManage: boolean }> {
  const res = await fetch(`${API}/api/patients/${patientId}/access`, {
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

  const accessToken = (session as any)?.accessToken as string | undefined;
  const currentUserEmail = (session?.user as any)?.email as string | undefined;
  const { caregivers, canManage } = accessToken
    ? await getCaregivers(id, accessToken).catch(() => ({ caregivers: [], canManage: false }))
    : { caregivers: [], canManage: false };

  const [openRequests, patientShares, documents, shareLinks] = await Promise.all([
    getOpenShareRequests(id).catch(() => []),
    getPatientShares(id).catch(() => []),
    getDocuments(id).catch(() => []),
    getShareLinks(id).catch(() => []),
  ]);

  const isAdmin = caregivers.some((c: any) => c.user_email === currentUserEmail && c.access_level === "admin");

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
        <SharingConsentPanel patientId={id} openRequests={openRequests} shares={patientShares} documents={documents} />
      </div>

      {shareLinks.length > 0 && (
        <div className="mb-6">
          <ShareLinksPanel patientId={id} links={shareLinks} documents={documents} />
        </div>
      )}

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
