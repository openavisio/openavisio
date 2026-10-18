import { redirect } from "next/navigation";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { auth } from "@/auth";
import { AppLayout } from "@/components/layout/AppLayout";
import { getAdminInvitations, getAdminUsers, getNotificationSettings, getOrganization } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { InviteUserButton } from "../admin/invitations/InviteUserButton";
import { CopyLinkButton } from "../admin/invitations/CopyLinkButton";
import { NotificationSettings } from "../admin/organization/NotificationSettings";
import { FamilyNameForm } from "./FamilyNameForm";
import { RemoveMemberButton, RevokeInvitationButton } from "./FamilyActions";

export const dynamic = "force-dynamic";

// ADR 052: the Household Manager's one page; the role is admin in code and never named here.
export default async function FamilyPage() {
  const [session, org] = await Promise.all([auth(), getOrganization().catch(() => null)]);
  const me = session?.user as any;
  if (me?.role !== "admin" || !org?.is_household) redirect("/");

  const t = await getTranslations("Family");
  const [users, invitations, notify] = await Promise.all([
    getAdminUsers().catch(() => []),
    getAdminInvitations().catch(() => []),
    getNotificationSettings().catch(() => ({ event_reminder: true, caregiver_added: true, invitation: true, include_content: false })),
  ]);
  const members = users.filter((u: any) => u.is_active);
  const open = invitations.filter((i: any) => !i.is_used && new Date(i.expires_at) > new Date());
  const card = "rounded-xl border bg-card p-6 space-y-4";

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("Title")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t("Subtitle")}</p>
      </div>

      <div className="max-w-2xl space-y-4">
        <section className={card}>
          <h2 className="font-medium text-sm">{t("Members")}</h2>
          <ul className="divide-y rounded-lg border">
            {members.map((u: any) => (
              <li key={u.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {[u.first_name, u.last_name].filter(Boolean).join(" ") || u.email}
                    {u.id === me.id && <span className="ml-2 text-xs text-muted-foreground">{t("You")}</span>}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                </div>
                {u.id !== me.id && <RemoveMemberButton id={u.id} name={u.first_name || u.email} />}
              </li>
            ))}
          </ul>
        </section>

        <section className={card}>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="font-medium text-sm">{t("Invitations")}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">{t("InvitationsHint")}</p>
            </div>
            <InviteUserButton />
          </div>
          {open.length > 0 && (
            <ul className="divide-y rounded-lg border">
              {open.map((i: any) => (
                <li key={i.id} className="flex items-center gap-3 px-4 py-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{i.email}</p>
                    <p className="text-xs text-muted-foreground">{t("ValidUntil", { date: formatDate(i.expires_at) })}</p>
                  </div>
                  <CopyLinkButton token={i.token} />
                  <RevokeInvitationButton id={i.id} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={card}>
          <h2 className="font-medium text-sm">{t("Record")}</h2>
          <FamilyNameForm initialName={org.name} initialLanguage={org.default_language ?? "de"} />
        </section>

        <NotificationSettings initial={notify} />

        <section className={card}>
          <div>
            <h2 className="font-medium text-sm">{t("Audit")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{t("AuditHint")}</p>
          </div>
          <Link href="/admin/audit" className="inline-block text-sm font-medium text-primary hover:underline">
            {t("AuditOpen")}
          </Link>
        </section>
      </div>
    </AppLayout>
  );
}
