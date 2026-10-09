"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { BookOpen, Loader2, Upload } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { IntakeForm } from "@/lib/intake";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const btnCls = "inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50";

export const STATUS_CLS: Record<IntakeForm["status"], string> = {
  reading: "bg-yellow-100 text-yellow-800",
  draft: "bg-blue-100 text-blue-800",
  released: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export function IntakeFormsView({ patientId, forms, children }: {
  patientId: string; forms: IntakeForm[]; children: React.ReactNode;
}) {
  const t = useTranslations("IntakeForms");
  const locale = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  // the form is read in the background; poll until it has been
  const reading = forms.some((f) => f.status === "reading");
  useEffect(() => {
    if (!reading) return;
    const id = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(id);
  }, [reading, router]);

  function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = new FormData(e.currentTarget);
    setError("");
    startTransition(async () => {
      const res = await fetch(`/api/intake-upload/${patientId}`, { method: "POST", body }).catch(() => null);
      if (!res?.ok) return setError(t("UploadError"));
      setOpen(false);
      router.push(`/patients/${patientId}/intake-forms/${(await res.json()).id}`);
    });
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {children}
        <div className="flex gap-2">
          <Link href={`/patients/${patientId}/intake-forms/history`} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm">
            <BookOpen className="h-4 w-4" />
            {t("History")}
          </Link>
          {!open && (
            <button onClick={() => setOpen(true)} className={btnCls}>
              <Upload className="h-4 w-4" />
              {t("Upload")}
            </button>
          )}
        </div>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">{t("Intro")}</p>
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {open && (
        <form onSubmit={upload} className="mb-6 space-y-4 rounded-xl border bg-card p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1">
              <span className="text-sm font-semibold">{t("TitleLabel")}</span>
              <input name="title" maxLength={256} className={inputCls} placeholder={t("TitlePlaceholder")} />
            </label>
            <label className="block space-y-1">
              <span className="text-sm font-semibold">{t("File")}</span>
              <input name="file" type="file" required accept=".pdf,.jpg,.jpeg,.png" className={inputCls} />
            </label>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={pending} className={btnCls}>
              {pending && <Loader2 className="h-4 w-4 animate-spin" />}
              {t("Upload")}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border px-3 py-1.5 text-sm">{t("Cancel")}</button>
          </div>
        </form>
      )}

      {forms.length ? (
        <div className="space-y-3">
          {forms.map((f) => (
            <Link key={f.id} href={`/patients/${patientId}/intake-forms/${f.id}`}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border bg-card p-4 text-sm hover:bg-accent">
              <span className="font-semibold">{f.title || f.file_name}</span>
              <span className="text-muted-foreground">{formatDate(f.created_at, locale)}</span>
              <span className={`ml-auto rounded px-2 py-0.5 text-xs ${STATUS_CLS[f.status]}`}>{t(`Status.${f.status}`)}</span>
            </Link>
          ))}
        </div>
      ) : (
        !open && <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      )}
    </div>
  );
}
