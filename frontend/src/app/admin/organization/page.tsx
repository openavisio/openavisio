import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getTranslations } from "next-intl/server";
import { OrgForm } from "./OrgForm";
import { NotificationSettings } from "./NotificationSettings";

const API = process.env.API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

export default async function AdminOrganizationPage() {
  const t = await getTranslations("Org");
  const session = await auth();
  const token = (session as any)?.accessToken;

  const res = await fetch(`${API}/api/organization`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!res.ok) {
    return (
      <AppLayout>
        <h1 className="text-xl font-bold">{t("Title")}</h1>
        <p className="text-sm text-destructive">{t("LoadFailed")}</p>
      </AppLayout>
    );
  }

  const org = await res.json();

  let notifySettings = { event_reminder: true, caregiver_added: true, invitation: true, include_content: false };
  try {
    const nRes = await fetch(`${API}/api/admin/notification-settings`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (nRes.ok) notifySettings = await nRes.json();
  } catch {}

  return (
    <AppLayout>
      <h1 className="text-xl font-bold">{t("Title")}</h1>
      <div className="max-w-lg space-y-4">
        <div className="rounded-xl border bg-card p-6 space-y-4">
          <div>
            <h2 className="font-medium text-sm">{t("SettingsTitle")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{t("SettingsHint")}</p>
          </div>
          <OrgForm
            initialName={org.name}
            initialDescription={org.description ?? null}
            initialLanguage={org.default_language ?? "en"}
            org={org}
          />
        </div>
        <NotificationSettings initial={notifySettings} />
      </div>
    </AppLayout>
  );
}
