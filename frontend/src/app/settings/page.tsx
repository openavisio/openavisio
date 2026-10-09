import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getLocale } from "next-intl/server";
import { cookies } from "next/headers";
import { getMe, getMyPasskeys } from "@/lib/api";
import { PasswordForm } from "./PasswordForm";
import { ProfileForm } from "./ProfileForm";
import { LanguagePicker } from "./LanguagePicker";
import { PasskeysSection } from "./PasskeysSection";
import { formatDate } from "@/lib/utils";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  manager: "Manager",
  user: "User",
};

export default async function SettingsPage() {
  const [session, locale, profile, cookieStore, passkeys] = await Promise.all([
    auth(),
    getLocale(),
    getMe().catch(() => null),
    cookies(),
    getMyPasskeys().catch(() => []),
  ]);
  const isSystem = !cookieStore.has("NEXT_LOCALE");
  const user = session?.user as any;

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account preferences</p>
      </div>

      {/* Account info */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <h2 className="font-medium text-sm">Account</h2>
        <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          <dt className="text-muted-foreground">Email</dt>
          <dd className="font-medium">{user?.email ?? "—"}</dd>
          <dt className="text-muted-foreground">Role</dt>
          <dd>
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
              {ROLE_LABELS[user?.role] ?? user?.role ?? "—"}
            </span>
          </dd>
          {profile?.last_login_at && (
            <>
              <dt className="text-muted-foreground">Last login</dt>
              <dd className="text-muted-foreground text-xs">{formatDate(profile.last_login_at)}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Profile */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">Profile</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Your display name across the app</p>
        </div>
        <ProfileForm
          initialFirstName={profile?.first_name ?? null}
          initialLastName={profile?.last_name ?? null}
        />
      </div>

      {/* Language */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <div>
          <h2 className="font-medium text-sm">Language</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Choose the display language for the interface</p>
        </div>
        <LanguagePicker current={locale} isSystem={isSystem} />
      </div>

      {/* Security */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">Security</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Change your login password</p>
        </div>
        <PasswordForm />
      </div>

      {/* Passkeys */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">Passkeys</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Sign in faster using your device&apos;s biometrics or a security key
          </p>
        </div>
        <PasskeysSection initialPasskeys={passkeys} />
      </div>
    </AppLayout>
  );
}
