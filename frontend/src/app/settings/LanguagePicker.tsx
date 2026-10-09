"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

export function LanguagePicker({ current, isSystem }: { current: string; isSystem: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function pick(code: string) {
    if (code === "system") {
      document.cookie = `NEXT_LOCALE=; path=/; max-age=0; SameSite=Lax`;
    } else {
      document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; SameSite=Lax`;
    }
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => pick("system")}
        disabled={pending}
        className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50
          ${isSystem
            ? "border-primary bg-primary/10 text-primary"
            : "hover:bg-muted"
          }`}
      >
        System
      </button>
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          onClick={() => pick(l.code)}
          disabled={pending}
          className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50
            ${!isSystem && current === l.code
              ? "border-primary bg-primary/10 text-primary"
              : "hover:bg-muted"
            }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
