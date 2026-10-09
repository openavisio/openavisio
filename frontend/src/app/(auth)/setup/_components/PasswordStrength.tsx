"use client";

import { useTranslations } from "next-intl";

interface Props {
  password: string;
}

function score(p: string): number {
  if (!p) return 0;
  let s = 0;
  if (p.length >= 8) s++;
  if (/[A-Z]/.test(p)) s++;
  if (/[0-9]/.test(p)) s++;
  if (/[^A-Za-z0-9]/.test(p)) s++;
  return s;
}

const colours = ["bg-destructive", "bg-orange-400", "bg-yellow-400", "bg-green-500"];
const labels = ["PasswordStrengthWeak", "PasswordStrengthFair", "PasswordStrengthGood", "PasswordStrengthStrong"] as const;

export function PasswordStrength({ password }: Props) {
  const t = useTranslations("Setup");
  const s = score(password);
  if (!password) return null;
  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${i <= s ? colours[s - 1] : "bg-muted"}`}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{t(labels[s - 1])}</p>
    </div>
  );
}
