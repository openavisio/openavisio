"use client";

import { useState } from "react";
import Image from "next/image";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { PasskeyButton } from "./PasskeyButton";

/** The demo instance hands its own credentials to the visitor — nobody arrives
 *  at a public demo already knowing the password. Rendered only when DEMO_MODE
 *  is on, so a real deployment never advertises an account. Values match
 *  `scripts/seed_demo.py`. */
const DEMO_ACCOUNTS = [
  { role: "Caregiver", email: "caregiver@demo.openavisio.org", password: "Demo123!Care" },
];

export function LoginForm({ demoMode = false }: { demoMode?: boolean }) {
  const t = useTranslations("Auth");
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const urlError = params.get("error");
  const registered = params.get("registered") === "true";
  const [error, setError] = useState(
    urlError === "SessionExpired" ? t("SessionExpired") : ""
  );
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const target = params.get("callbackUrl") || "/";
      // Without redirectTo next-auth returns the current URL, and on
      // /login?error=SessionExpired it read that "error" as a failed sign-in.
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
        redirectTo: target,
      });
      if (result?.error) {
        // Only CredentialsSignin means the password was wrong. Everything else
        // is our side failing, and calling that a bad password sent the tester
        // hunting for a typo that was not there.
        setError(result.error === "CredentialsSignin" ? t("InvalidCredentials") : t("SignInFailed"));
      } else {
        router.push(target);
      }
    } catch (err) {
      console.error("Login error:", err);
      setError(t("InvalidCredentials"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40">
      <div className="w-full max-w-md">
        <div className="bg-card rounded-xl shadow-lg p-8 space-y-6">
          <div className="text-center">
            <Image src="/logo.png" alt="OpenAvisio" width={80} height={80} className="mx-auto mb-3" />
            <p className="text-muted-foreground">{t("SignIn")}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {registered && (
              <div className="rounded-lg bg-green-500/10 text-green-700 dark:text-green-400 px-4 py-3 text-sm">
                {t("AccountCreated")}
              </div>
            )}
            {error && (
              <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("Email")}</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
                placeholder={t("EmailPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("Password")}</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? "..." : t("SignIn")}
            </button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">{t("Or")}</span>
            </div>
          </div>

          <PasskeyButton />

          {demoMode && (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-xs">
              <p className="mb-2 font-medium">{t("DemoTitle")}</p>
              <div className="space-y-1.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <button
                    key={a.email}
                    type="button"
                    onClick={() => { setEmail(a.email); setPassword(a.password); setError(""); }}
                    className="flex w-full items-baseline justify-between gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-primary/10"
                  >
                    <span className="min-w-0 truncate font-mono">{a.email}</span>
                    <span className="shrink-0 font-mono text-muted-foreground">{a.password}</span>
                  </button>
                ))}
              </div>
              <p className="mt-2 text-muted-foreground">{t("DemoHint")}</p>
            </div>
          )}

          <p className="text-center text-xs text-muted-foreground pt-2">
            <a href="/recover" className="underline hover:text-foreground">{t("LostAccess")}</a>
          </p>

          <p className="text-center text-xs text-muted-foreground">
            <a href="/privacy" className="underline hover:text-foreground">Datenschutzerklärung</a>
            {" · "}
            <a href="/imprint" className="underline hover:text-foreground">Impressum</a>
          </p>
        </div>
      </div>
    </div>
  );
}

