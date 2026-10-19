import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getLocale, getTranslations } from "next-intl/server";
import { cookies, headers } from "next/headers";
import { getMe, getMyPasskeys, getOrganization } from "@/lib/api";
import { PasswordForm } from "./PasswordForm";
import { ProfileForm } from "./ProfileForm";
import { LanguagePicker } from "./LanguagePicker";
import { PasskeysSection } from "./PasskeysSection";
import { formatDate } from "@/lib/utils";

export default async function SettingsPage() {
  const [session, locale, profile, cookieStore, passkeys] = await Promise.all([
    auth(),
    getLocale(),
    getMe().catch(() => null),
    cookies(),
    getMyPasskeys().catch(() => []),
  ]);
  const isHousehold = (await getOrganization().catch(() => null))?.is_household ?? false;
  const t = await getTranslations("Subscription");
  const s = await getTranslations("SettingsPage");
  const host = (await headers()).get("host");
  const isSystem = !cookieStore.has("NEXT_LOCALE");
  const user = session?.user as any;

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{s("Title")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{s("Subtitle")}</p>
      </div>

      {/* Account info */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <h2 className="font-medium text-sm">{s("Account")}</h2>
        <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          <dt className="text-muted-foreground">{s("Email")}</dt>
          <dd className="font-medium">{user?.email ?? "—"}</dd>
          {/* ADR 052: a household never reads "admin" */}
          {!isHousehold && (
            <>
              <dt className="text-muted-foreground">{s("Role")}</dt>
              <dd>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                  {["admin", "manager", "user"].includes(user?.role) ? s(`Roles.${user.role}`) : user?.role ?? "—"}
                </span>
              </dd>
            </>
          )}
          {profile?.last_login_at && (
            <>
              <dt className="text-muted-foreground">{s("LastLogin")}</dt>
              <dd className="text-muted-foreground text-xs">{formatDate(profile.last_login_at)}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Profile */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">{s("Profile")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{s("ProfileHint")}</p>
        </div>
        <ProfileForm
          initialFirstName={profile?.first_name ?? null}
          initialLastName={profile?.last_name ?? null}
        />
      </div>

      {/* Language */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <div>
          <h2 className="font-medium text-sm">{s("Language")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{s("LanguageHint")}</p>
        </div>
        <LanguagePicker current={locale} isSystem={isSystem} />
      </div>

      {/* Security */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">{s("Security")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{s("SecurityHint")}</p>
        </div>
        <PasswordForm />
      </div>

      {/* Passkeys */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">Passkeys</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {s("PasskeysHint")}
          </p>
        </div>
        <PasskeysSection initialPasskeys={passkeys} />
      </div>

      {/* § 312k BGB: a hosted household cancels on the operator's page (avisiohub site/kuendigung.html) */}
      {process.env.HOSTED_SETUP === "true" && user?.role === "admin" && (
        <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
          <h2 className="font-medium text-sm">{t("Title")}</h2>
          <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
            <dt className="text-muted-foreground">{t("Address")}</dt>
            <dd className="font-medium break-all">{host}</dd>
            <dt className="text-muted-foreground">{t("Operator")}</dt>
            <dd>
              Martin Riedel ·{" "}
              <a href="mailto:info@openavisio.app" className="text-primary hover:underline">info@openavisio.app</a>
              <div className="text-xs mt-0.5">
                <a href="/imprint" className="text-muted-foreground hover:underline">Impressum</a> ·{" "}
                <a href="/privacy" className="text-muted-foreground hover:underline">Datenschutz</a>
              </div>
            </dd>
          </dl>
          <p className="text-xs text-muted-foreground">{t("Billing")}</p>
          <p className="text-xs text-muted-foreground">{t("AfterCancel")}</p>
          <div className="flex flex-col items-start gap-1 text-sm font-medium text-primary">
            <a href="https://billing.stripe.com/p/login/8x228qbDI4pH8Hk63P7Vm00" className="hover:underline">{t("Portal")}</a>
            <a href="https://openavisio.app/kuendigung.html" className="hover:underline">{t("Cancel")}</a>
            <a href={`mailto:info@openavisio.app?subject=${encodeURIComponent(t("MailSubject"))}&body=${encodeURIComponent(t("MailBody", { host: host ?? "" }))}`} className="hover:underline">
              {t("MailCancel")}
            </a>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
