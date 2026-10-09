"use client";

import { useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { AlertTriangle, Check, Copy, Download, Link2, ShieldAlert } from "lucide-react";
import { createShareLinkAction } from "../share-link-actions";
import { downloadHandoutPdf } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { Handout } from "@/lib/handout";

const BY_PERIOD = "carer_updates";

function within(date: string | null, p: { from: string; to: string }) {
  return !!date && !!p.from && !!p.to && date.slice(0, 10) >= p.from && date.slice(0, 10) <= p.to;
}

export function HandoutPreview({ patientId, handout, children }: { patientId: string; handout: Handout; children: React.ReactNode }) {
  const t = useTranslations("Handout");
  const locale = useLocale();
  // ADR 048: starts from the variant on every visit
  const [excluded, setExcluded] = useState<Set<string>>(
    () => new Set(handout.sections.filter((s) => !s.preselected).flatMap((s) => s.entries.map((e) => e.id))),
  );
  const [lang, setLang] = useState(locale === "de" ? "de" : "en");
  // ADR 049: Carer Updates are offered by period, empty until picked
  const [period, setPeriod] = useState({ from: "", to: "" });
  const [error, setError] = useState("");
  const [expiry, setExpiry] = useState(30);
  const [sharedUrl, setSharedUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();
  const sections = handout.sections.filter((s) => s.entries.length);

  function toggle(id: string) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  function pickPeriod(next: { from: string; to: string }) {
    setPeriod(next);
    const entries = handout.sections.filter((s) => s.key === BY_PERIOD).flatMap((s) => s.entries);
    setExcluded((prev) => {
      const out = new Set(prev);
      for (const e of entries) {
        if (within(e.date, next)) out.delete(e.id);
        else out.add(e.id);
      }
      return out;
    });
  }

  // ADR 048: the link carries the Handout frozen exactly as previewed here
  function share() {
    setError("");
    startTransition(async () => {
      const r = await createShareLinkAction(patientId, [], expiry, { variant: handout.variant, exclude: [...excluded], lang });
      if (r.error) setError(t("ShareError"));
      else setSharedUrl(r.url ?? "");
    });
  }

  function download() {
    setError("");
    startTransition(async () => {
      try {
        const b64 = await downloadHandoutPdf(patientId, handout.variant, [...excluded], lang);
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${t(`title.${handout.variant}`)} ${handout.patient.name}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        setError(t("DownloadError"));
      }
    });
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        {children}
        <div className="flex items-center gap-2">
          <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t("Language")}
            className="rounded-lg border bg-background px-2 py-1.5 text-sm">
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
          <button onClick={download} disabled={pending}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
            <Download className="h-4 w-4" />
            {t("Download")}
          </button>
        </div>
      </div>
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
      <div className="mb-4 rounded-xl border p-3 text-sm">
        {sharedUrl !== null ? (
          <div className="space-y-2">
            <p className="flex items-start gap-2 text-xs text-amber-800 dark:text-amber-300">
              <ShieldAlert className="size-4 shrink-0" />
              {t("ShareCopyOnce")}
            </p>
            <div className="flex items-center gap-2">
              <input readOnly value={sharedUrl} onFocus={(e) => e.currentTarget.select()}
                className="flex-1 rounded-lg border bg-muted px-3 py-2 font-mono text-sm" />
              <button onClick={async () => { await navigator.clipboard.writeText(sharedUrl); setCopied(true); }}
                className="flex items-center gap-1.5 rounded-lg border px-3 py-2 font-medium hover:bg-muted">
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                {copied ? t("Copied") : t("Copy")}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">{t("ShareHint")}</span>
            <select value={expiry} onChange={(e) => setExpiry(Number(e.target.value))} aria-label={t("ShareExpiry")}
              className="rounded-lg border bg-background px-2 py-1.5">
              {[7, 30, 90].map((d) => <option key={d} value={d}>{t("Days", { count: d })}</option>)}
            </select>
            <button onClick={share} disabled={pending}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-medium hover:bg-muted disabled:opacity-50">
              <Link2 className="size-4" />
              {t("Share")}
            </button>
          </div>
        )}
      </div>
      <p className="mb-4 text-sm text-muted-foreground">{t("Hint")}</p>
      {handout.missing.map((m) => (
        <p key={m} className="mb-4 flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
          <AlertTriangle className="size-4 shrink-0" />
          {t(`missing.${m}`)}
          <Link href={`/patients/${patientId}/${m.replace("_", "-")}`} className="font-medium underline">{t("CreateNow")}</Link>
        </p>
      ))}

      <div className="space-y-4 rounded-xl border bg-card p-4 sm:p-6">
        <div>
          <h1 className="text-lg font-semibold">{t(`title.${handout.variant}`)}: {handout.patient.name}</h1>
          {handout.patient.birth_date && (
            <p className="text-sm text-muted-foreground">{t("Born")} {formatDate(handout.patient.birth_date, locale)}</p>
          )}
        </div>
        {sections.length === 0 && <p className="text-sm text-muted-foreground">{t("Empty")}</p>}
        {sections.map((s) => (
          <section key={s.key}>
            <h2 className="mb-1 border-b pb-1 text-sm font-semibold">{t(`section.${s.key}`)}</h2>
            {s.key === BY_PERIOD && (
              <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
                <label className="flex items-center gap-2">
                  {t("PeriodFrom")}
                  <input type="date" value={period.from} className="rounded-lg border bg-background px-2 py-1"
                    onChange={(e) => pickPeriod({ ...period, from: e.target.value })} />
                </label>
                <label className="flex items-center gap-2">
                  {t("PeriodTo")}
                  <input type="date" value={period.to} className="rounded-lg border bg-background px-2 py-1"
                    onChange={(e) => pickPeriod({ ...period, to: e.target.value })} />
                </label>
              </div>
            )}
            <ul className="space-y-1">
              {s.entries.filter((e) => s.key !== BY_PERIOD || within(e.date, period)).map((e) => (
                <li key={e.id}>
                  <label className={`flex cursor-pointer items-start gap-2 text-sm ${excluded.has(e.id) ? "text-muted-foreground line-through" : ""}`}>
                    <input type="checkbox" className="mt-0.5" checked={!excluded.has(e.id)} onChange={() => toggle(e.id)} />
                    <span>
                      <span className="font-medium">{e.text}</span>
                      {e.suspected && (
                        <span className="ml-1.5 rounded border border-amber-600 px-1 text-xs text-amber-700 dark:text-amber-400">{t("Suspected")}</span>
                      )}
                      {e.retold && <span className="ml-1.5 rounded border px-1 text-xs text-muted-foreground">{t("Retold")}</span>}
                      {e.detail && <span> {e.detail}</span>}
                      {e.date && <span className="text-muted-foreground"> {formatDate(e.date, locale)}</span>}
                      {e.items.length > 0 && (
                        <ol className="mt-1 list-decimal pl-5">
                          {e.items.map((i, n) => (
                            <li key={n}>
                              {i.text}
                              {i.flag && (
                                <span className="ml-1.5 rounded border border-destructive px-1 text-xs text-destructive">{t(`flag.${i.flag}`)}</span>
                              )}
                            </li>
                          ))}
                        </ol>
                      )}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
