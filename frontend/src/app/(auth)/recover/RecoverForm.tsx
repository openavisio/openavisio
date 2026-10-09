"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";

/** ADR 044: the way back in for a household that has one login and nobody to
 *  ask. Sets a password and nothing else — no session is issued here, so this
 *  can never become a way around a second factor. */
export function RecoverForm() {
  const t = useTranslations("Auth");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [freshCode, setFreshCode] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError(t("PasswordTooShort"));
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/backend/auth/recover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, recovery_code: code, new_password: password }),
      });
      if (res.ok) {
        const data = await res.json();
        setFreshCode(data.recovery_code || "");
      } else {
        setError(res.status === 429 ? t("TooManyAttempts") : t("InvalidRecoveryCode"));
      }
    } catch {
      setError(t("SignInFailed"));
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
            <p className="text-muted-foreground">{t("RecoverTitle")}</p>
          </div>

          {freshCode ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-green-500/10 text-green-700 dark:text-green-400 px-4 py-3 text-sm">
                {t("RecoverDone")}
              </div>
              {/* The code they just used is spent. This one replaces it, and it
                  is shown exactly once, here. */}
              <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 p-4 space-y-2">
                <p className="text-xs text-muted-foreground">{t("RecoverFreshCode")}</p>
                <code className="block rounded bg-background px-3 py-2 font-mono text-sm tracking-widest select-all">
                  {freshCode}
                </code>
              </div>
              <Link
                href="/login"
                className="block w-full rounded-lg bg-primary text-primary-foreground py-2 text-center text-sm font-medium hover:bg-primary/90"
              >
                {t("SignIn")}
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-muted-foreground">{t("RecoverBody")}</p>
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
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("RecoveryCode")}</label>
                <input
                  type="text"
                  required
                  autoComplete="off"
                  spellCheck={false}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="XXXXX-XXXXX-XXXXX-XXXXX"
                  className="w-full rounded-lg border px-3 py-2 font-mono text-sm tracking-widest focus:outline-none focus:ring-2 focus:ring-primary bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("NewPassword")}</label>
                <input
                  type="password"
                  required
                  minLength={8}
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
                {loading ? "..." : t("RecoverSubmit")}
              </button>
              <p className="text-center text-xs text-muted-foreground">
                <Link href="/login" className="underline hover:text-foreground">
                  {t("BackToLogin")}
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
