"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { updateDocument } from "@/lib/api";

// what this table reads from GET /patients/{id}/documents
export type FactsDoc = {
  id: string;
  type?: string | null;
  file_name?: string | null;
  document_classification?: string | null;
  detected_provider?: string | null;
  correspondent?: { id: string; name: string } | null;
  issued_date?: string | null;
  verification_status?: string | null;
};

type Flag = "noDate" | "beforeBirth" | "future" | "kindOther";

function flagsOf(d: FactsDoc, birth: string | null, today: string): Flag[] {
  const f: Flag[] = [];
  if (!d.issued_date) f.push("noDate");
  else if (birth && d.issued_date < birth) f.push("beforeBirth");
  else if (d.issued_date > today) f.push("future");
  // the kind is the User's own type, else what the classification found; "other" found nothing
  if (!d.type && (!d.document_classification || d.document_classification === "other")) f.push("kindOther");
  return f;
}

// ADR 058 step 1: every letter's date and kind before anything else, because every later step orders by
// the date. The unusual ones first; the rest folded away.
export function DocumentFacts({ patientId, docs, birthDate }: { patientId: string; docs: FactsDoc[]; birthDate: string | null }) {
  const t = useTranslations("ProposalReview");
  const tc = useTranslations("DocDetail");  // class_* labels live with the detail page
  const [today] = useState(() => new Date().toISOString().slice(0, 10));
  const [showAll, setShowAll] = useState(false);
  const kindOf = (d: FactsDoc) => d.type
    || (d.document_classification && d.document_classification !== "other" && tc.has(`class_${d.document_classification}`)
      ? tc(`class_${d.document_classification}`) : "");
  const kinds = [...new Set(docs.map(kindOf).filter(Boolean))].sort();
  const rows = docs
    .filter((d) => d.verification_status === "extracted" || !d.issued_date)
    .map((d) => ({ d, flags: flagsOf(d, birthDate, today) }))
    .sort((a, b) => b.flags.length - a.flags.length || (b.d.issued_date ?? "").localeCompare(a.d.issued_date ?? ""));
  const unusual = rows.filter((r) => r.flags.length > 0);
  const shown = showAll ? rows : unusual;
  if (rows.length === 0) return null;

  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-semibold">{t("Facts")}</h2>
        <p className="text-sm text-muted-foreground">{t("FactsIntro")}</p>
      </div>
      {unusual.length === 0 && !showAll && <p className="text-sm text-muted-foreground">{t("FactsAllFine")}</p>}
      {shown.length > 0 && (
        <ul className="divide-y rounded-xl border bg-card">
          {shown.map(({ d, flags }) => (
            <FactRow key={d.id} patientId={patientId} doc={d} kind={kindOf(d)} flags={flags} />
          ))}
        </ul>
      )}
      {rows.length > unusual.length && (
        <button onClick={() => setShowAll((s) => !s)} className="text-sm text-primary hover:underline">
          {showAll ? t("FactsOnlyUnusual") : t("FactsShowAll", { count: rows.length - unusual.length })}
        </button>
      )}
      <datalist id="doc-kinds">{kinds.map((k) => <option key={k} value={k} />)}</datalist>
    </section>
  );
}

function FactRow({ patientId, doc, kind: shownKind, flags }: { patientId: string; doc: FactsDoc; kind: string; flags: Flag[] }) {
  const t = useTranslations("ProposalReview");
  const router = useRouter();
  const [date, setDate] = useState(doc.issued_date ?? "");
  const [kind, setKind] = useState(shownKind);
  const [error, setError] = useState(false);
  const [pending, startTransition] = useTransition();

  function save(data: { issued_date?: string | null; type?: string | null }) {
    setError(false);
    startTransition(async () => {
      try {
        await updateDocument(doc.id, data);
        router.refresh();
      } catch {
        setError(true);
      }
    });
  }

  const sender = doc.correspondent?.name || doc.detected_provider;
  return (
    <li className="space-y-2 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <a href={`/patients/${patientId}/documents/${doc.id}`} target="_blank" rel="noopener"
           className="min-w-0 truncate font-medium text-primary hover:underline">
          {sender || doc.file_name || "—"}
        </a>
        <span className="flex flex-wrap gap-1">
          {flags.map((f) => (
            <span key={f} className="rounded bg-amber-500/15 px-1.5 text-xs text-amber-800 dark:text-amber-300">
              {t(`flag_${f}`)}
            </span>
          ))}
        </span>
      </div>
      {!sender && doc.file_name && <p className="truncate text-xs text-muted-foreground">{doc.file_name}</p>}
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          {t("FactsDate")}
          <input
            type="date"
            value={date}
            disabled={pending}
            onChange={(e) => setDate(e.target.value)}
            onBlur={() => date !== (doc.issued_date ?? "") && save({ issued_date: date || null })}
            className="rounded-md border bg-background px-2 py-1 text-sm text-foreground"
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          {t("FactsKind")}
          <input
            list="doc-kinds"
            value={kind}
            disabled={pending}
            onChange={(e) => setKind(e.target.value)}
            onBlur={() => kind.trim() !== shownKind && save({ type: kind.trim() || null })}
            className="w-44 rounded-md border bg-background px-2 py-1 text-sm text-foreground"
          />
        </label>
      </div>
      {error && <p className="text-xs text-destructive">{t("SaveError")}</p>}
    </li>
  );
}
