import { Suspense } from "react";
import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { RegisterForm } from "./RegisterForm";
import { OpenInAppLink } from "./OpenInAppLink";

async function RegisterContent({ token }: { token: string }) {
  const t = await getTranslations("Auth");

  if (!token) {
    return (
      <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm text-center">
        {t("InvalidInvitation")}
      </div>
    );
  }

  // Validate token and get email server-side
  let email: string | null = null;
  let tokenError: string | null = null;
  try {
    const res = await fetch(
      `${process.env.API_URL || "http://localhost:8000"}/api/auth/invite?token=${encodeURIComponent(token)}`,
      { cache: "no-store" }
    );
    if (res.ok) {
      const data = await res.json();
      email = data.email;
    } else if (res.status === 409) {
      tokenError = t("InvitationAlreadyUsed");
    } else {
      const data = await res.json().catch(() => ({}));
      const detail: string = data?.detail ?? "";
      tokenError = detail.toLowerCase().includes("expired") ? t("InvitationExpired") : t("InvalidInvitation");
    }
  } catch {
    tokenError = t("ServerUnavailable");
  }

  if (tokenError) {
    return (
      <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm text-center">
        {tokenError}
      </div>
    );
  }

  return (
    <>
      <RegisterForm email={email!} />
      <OpenInAppLink token={token} />
    </>
  );
}

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token = "" } = await searchParams;
  const t = await getTranslations("Auth");

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40">
      <div className="w-full max-w-md">
        <div className="bg-card rounded-xl shadow-lg p-8 space-y-6">
          <div className="text-center">
            <Image src="/logo.png" alt="OpenAvisio" width={80} height={80} className="mx-auto mb-3" />
            <p className="text-muted-foreground">{t("CreateAccount")}</p>
          </div>
          <Suspense fallback={<div className="text-center text-sm text-muted-foreground">Loading…</div>}>
            <RegisterContent token={token} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
