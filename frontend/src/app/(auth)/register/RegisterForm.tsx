"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { registerAction } from "./actions";

export function RegisterForm({ email }: { email: string }) {
  const t = useTranslations("Auth");
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("PasswordMismatch"));
      return;
    }
    if (password.length < 8) {
      setError(t("PasswordTooShort"));
      return;
    }
    if (!consent) {
      setError(t("ConsentRequired"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await registerAction(token, firstName, lastName, password, consent);
      if (result.error) {
        setError(result.error);
      } else {
        router.push("/login?registered=true");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">{error}</div>
      )}
      <div className="space-y-2">
        <label className="text-sm font-medium">{t("Email")}</label>
        <input
          type="email"
          value={email}
          readOnly
          className="w-full rounded-lg border px-3 py-2 text-sm bg-muted text-muted-foreground cursor-not-allowed"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <label className="text-sm font-medium">{t("FirstName")}</label>
          <input
            type="text"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">{t("LastName")}</label>
          <input
            type="text"
            required
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
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
      <div className="space-y-2">
        <label className="text-sm font-medium">{t("ConfirmPassword")}</label>
        <input
          type="password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
        />
      </div>
      <label className="flex items-start gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 size-4 shrink-0"
        />
        <span>
          {t("ConsentText")}
        </span>
      </label>
      <button
        type="submit"
        disabled={loading || !consent}
        className="w-full rounded-lg bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
      >
        {loading ? "..." : t("CreateAccount")}
      </button>
    </form>
  );
}
