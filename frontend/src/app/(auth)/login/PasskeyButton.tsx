"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

export function PasskeyButton() {
  const t = useTranslations("Auth");
  const router = useRouter();
  const params = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handlePasskey() {
    if (!window.PublicKeyCredential) {
      setError(t("PasskeyNotSupported"));
      return;
    }
    setLoading(true);
    setError("");

    try {
      const beginRes = await fetch("/api/auth/passkey/authenticate/begin");
      if (!beginRes.ok) throw new Error("begin failed");
      const options = await beginRes.json();

      const { startAuthentication } = await import("@simplewebauthn/browser");
      const assertion = await startAuthentication({ optionsJSON: options });

      const result = await signIn("passkey", {
        credential: JSON.stringify(assertion),
        redirect: false,
      });

      if (result?.error) {
        setError(t("PasskeyError"));
      } else {
        router.push(params.get("callbackUrl") || "/patients");
      }
    } catch (e: any) {
      if (e?.name !== "NotAllowedError") {
        setError(t("PasskeyError"));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          {error}
        </div>
      )}
      <button
        type="button"
        onClick={handlePasskey}
        disabled={loading}
        className="w-full rounded-lg border border-border bg-background py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
      >
        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 11V7a5 5 0 0 1 10 0v4M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z" />
        </svg>
        {loading ? "..." : t("SignInWithPasskey")}
      </button>
    </div>
  );
}
