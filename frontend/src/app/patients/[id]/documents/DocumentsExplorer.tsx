"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/hooks/use-mobile";
import { useLocale, useTranslations } from "next-intl";
import {
  FileText, ClipboardCheck, Eye, Search, X, Download, Star, Loader2,
  FlaskConical, Pill, Activity, Scan, FileHeart,
} from "lucide-react";
import { getDocuments } from "@/lib/api";
import { formatDate, statusBadgeColor } from "@/lib/utils";
import { RetryButton } from "./UploadPanel";
import { FavoriteButton } from "./FavoriteButton";
import { DeleteDocumentButton } from "./[docId]/DeleteDocumentButton";

type Doc = any;

const RANGES = { "3m": 91, "12m": 365, all: Infinity } as const;
type RangeKey = keyof typeof RANGES;

// Every non-terminal pipeline status set by backend/app/workers/pipeline.py.
// Miss one and the poll stops mid-run, leaving the row stuck until a manual
// reload. Terminal: completed, failed.
const IN_PROGRESS = new Set([
  "pending", "ocr_processing", "ocr_done", "classifying", "classified", "extracting", "extracted", "embedding",
]);

// Icon + tint per document class, so the list is scannable by shape and colour
// before a single word is read. Unknown class falls back to a plain page.
const LOOKS: Record<string, { Icon: typeof FileText; tint: string }> = {
  lab_report: { Icon: FlaskConical, tint: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  doctor_letter: { Icon: FileText, tint: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  therapy_report: { Icon: Activity, tint: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  prescription: { Icon: Pill, tint: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  imaging_report: { Icon: Scan, tint: "bg-violet-500/10 text-violet-600 dark:text-violet-400" },
  discharge_summary: { Icon: FileHeart, tint: "bg-rose-500/10 text-rose-600 dark:text-rose-400" },
};
const FALLBACK_LOOK = { Icon: FileText, tint: "bg-muted text-muted-foreground" };
const docLook = (cls?: string) => (cls && LOOKS[cls]) || FALLBACK_LOOK;

// A caregiver-readable heading. The file name is often a scanner artefact
// ("img20240405_08273634.pdf"), so it is the last resort, not the first.
function docTitle(doc: Doc, t: (k: string) => string, tc: (k: string) => string): string {
  if (doc.type) return doc.type;
  if (doc.document_classification && LOOKS[doc.document_classification]) {
    return tc(`class_${doc.document_classification}`);
  }
  return doc.description || doc.file_name || t("unnamed");
}

// The pipeline in order. A bare "extracting…" says nothing about how far along
// a document is; four dots and a spinner do, and they sit in the card body
// rather than wedged between the buttons.
const STAGES = ["ocr", "classification", "extraction", "embedding"];

function PipelineProgress({ stage, label }: { stage?: string; label: string }) {
  const at = STAGES.indexOf(stage ?? "");
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" />
      <span className="truncate">{label}</span>
      <span className="flex items-center gap-1 shrink-0" aria-hidden>
        {STAGES.map((s, i) => (
          <span
            key={s}
            className={`h-1 w-4 rounded-full transition-colors ${
              i < at ? "bg-primary/60" : i === at ? "bg-primary animate-pulse" : "bg-muted"
            }`}
          />
        ))}
      </span>
    </div>
  );
}

type SortKey = "doc" | "added";

function docDate(doc: Doc, sortBy: SortKey = "doc"): Date {
  return new Date(sortBy === "added" ? doc.created_at : (doc.issued_date ?? doc.created_at));
}

function needsAction(doc: Doc): boolean {
  return doc.processing_status === "failed" || doc.verification_status === "extracted";
}

export function DocumentsExplorer({
  patientId,
  initialDocuments,
}: {
  patientId: string;
  initialDocuments: Doc[];
}) {
  const t = useTranslations("DocumentsPage");
  const tc = useTranslations("DocDetail");  // class_* labels live with the detail page
  const locale = useLocale();
  const [docs, setDocs] = useState<Doc[]>(initialDocuments);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [corr, setCorr] = useState("");
  const [range, setRange] = useState<RangeKey>("all");
  const [sortBy, setSortBy] = useState<SortKey>("doc");
  const [action, setAction] = useState(false);
  const [onlyFavs, setOnlyFavs] = useState(false);
  const [revealed, setRevealed] = useState<string | null>(null);
  const router = useRouter();
  const isMobile = useIsMobile();
  const [searching, setSearching] = useState(false);
  const qRef = useRef(q);
  qRef.current = q;

  // server refresh (upload finished → router.refresh) replaces the base list
  useEffect(() => setDocs(initialDocuments), [initialDocuments]);

  // content search: debounced round-trip to the backend `q` filter
  useEffect(() => {
    const trimmed = q.trim();
    setSearching(true);
    const handle = setTimeout(() => {
      getDocuments(patientId, trimmed ? { q: trimmed } : undefined)
        .then((d) => { if (qRef.current === q) setDocs(d); })
        .catch(() => {})
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [q, patientId]);

  // live processing status: poll while any document is still in the pipeline
  const hasActive = docs.some((d) => IN_PROGRESS.has(d.processing_status));
  useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(() => {
      const trimmed = qRef.current.trim();
      getDocuments(patientId, trimmed ? { q: trimmed } : undefined)
        .then(setDocs)
        .catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [hasActive, patientId]);

  const types = useMemo(() => {
    const m = new Map<string, number>();
    docs.forEach((d) => d.type && m.set(d.type, (m.get(d.type) ?? 0) + 1));
    return [...m.entries()].sort();
  }, [docs]);

  const correspondents = useMemo(() => {
    const m = new Map<string, { name: string; count: number }>();
    docs.forEach((d) => {
      if (!d.correspondent) return;
      const e = m.get(d.correspondent.id);
      m.set(d.correspondent.id, { name: d.correspondent.name, count: (e?.count ?? 0) + 1 });
    });
    return [...m.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name));
  }, [docs]);

  const cutoff = Date.now() - RANGES[range] * 86_400_000;
  const filtered = docs.filter(
    (d) =>
      (!type || d.type === type) &&
      (!corr || d.correspondent?.id === corr) &&
      (range === "all" || docDate(d, sortBy).getTime() >= cutoff) &&
      (!action || needsAction(d)) &&
      (!onlyFavs || d.is_favorite)
  );

  // month groups (newest first) — timeline anchors for long lists
  const monthFmt = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" });
  const groups: { label: string; docs: Doc[] }[] = [];
  [...filtered]
    .sort((a, b) => docDate(b, sortBy).getTime() - docDate(a, sortBy).getTime())
    .forEach((d) => {
      const label = monthFmt.format(docDate(d, sortBy));
      const last = groups[groups.length - 1];
      if (last?.label === label) last.docs.push(d);
      else groups.push({ label, docs: [d] });
    });

  const hasFilters = q.trim() || type || corr || range !== "all" || action || onlyFavs;
  const reset = () => { setQ(""); setType(""); setCorr(""); setRange("all"); setAction(false); setOnlyFavs(false); };

  const selectCls =
    "rounded-lg border border-input bg-card px-2.5 py-1.5 text-sm text-foreground max-w-40";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded-lg border border-input bg-card pl-9 pr-3 py-1.5 text-sm"
          />
        </div>
        <select value={type} onChange={(e) => setType(e.target.value)} className={selectCls}>
          <option value="">{t("allTypes")}</option>
          {types.map(([name, count]) => (
            <option key={name} value={name}>{name} ({count})</option>
          ))}
        </select>
        <select value={corr} onChange={(e) => setCorr(e.target.value)} className={selectCls}>
          <option value="">{t("allCorrespondents")}</option>
          {correspondents.map(([id, { name, count }]) => (
            <option key={id} value={id}>{name} ({count})</option>
          ))}
        </select>
        <select value={range} onChange={(e) => setRange(e.target.value as RangeKey)} className={selectCls}>
          <option value="all">{t("rangeAll")}</option>
          <option value="12m">{t("range12m")}</option>
          <option value="3m">{t("range3m")}</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
          <input type="checkbox" checked={action} onChange={(e) => setAction(e.target.checked)} />
          {t("actionNeeded")}
        </label>

        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input type="checkbox" checked={onlyFavs} onChange={(e) => setOnlyFavs(e.target.checked)} />
          <Star className="size-3.5 text-amber-500" fill="currentColor" />
          {t("onlyFavorites")}
        </label>
      </div>

      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-3">
          <span>
            {searching
              ? t("searching")
              : t("countShown", { shown: filtered.length, total: docs.length })}
          </span>
          {hasFilters && (
            <button onClick={reset} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              <X className="h-3 w-3" />
              {t("reset")}
            </button>
          )}
        </div>
        <div className="inline-flex items-center rounded-md border border-border p-0.5">
          {(["doc", "added"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setSortBy(k)}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                sortBy === k ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t(k === "doc" ? "sortByDocDate" : "sortByAdded")}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {docs.length === 0 ? t("noDocuments") : t("noMatches")}
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.label} className="space-y-3">
              <div className="flex items-center gap-3 pt-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground shrink-0">
                  {group.label}
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>
              {group.docs.map((doc) => {
                const { Icon, tint } = docLook(doc.document_classification);
                const ins = doc.insights;
                const issuer = doc.detected_provider || ins?.provider || doc.correspondent?.name;
                const counts = [
                  ins?.observations && t("countObservations", { count: ins.observations }),
                  ins?.medications && t("countMedications", { count: ins.medications }),
                  ins?.diagnoses && t("countDiagnoses", { count: ins.diagnoses }),
                  ins?.recommendations && t("countRecommendations", { count: ins.recommendations }),
                ].filter(Boolean);
                const open = revealed === doc.id;
                return (
            <div key={doc.id} className="overflow-hidden rounded-xl border bg-card">
             <div className="flex items-stretch">
              {/* On a phone the first tap reveals the actions, the second opens
                  the document — the action column has no room next to the text. */}
              <div
                onClick={isMobile ? () => (open ? router.push(`/patients/${patientId}/documents/${doc.id}`) : setRevealed(doc.id)) : undefined}
                className="flex flex-1 items-center gap-3 min-w-0 p-4 lg:items-start"
              >
                <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${tint}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="font-medium text-sm truncate">
                      {docTitle(doc, t, tc)}
                      {issuer && <span className="text-muted-foreground font-normal">{" · "}{issuer}</span>}
                    </span>
                    {(!isMobile || open) && (
                      <FavoriteButton docId={doc.id} patientId={patientId} initial={!!doc.is_favorite} />
                    )}
                  </div>

                  {IN_PROGRESS.has(doc.processing_status) && (
                    <PipelineProgress stage={doc.pipeline_stage} label={
                      doc.pipeline_stage ? t(`stage_${doc.pipeline_stage}`) : t("processing")
                    } />
                  )}

                  {/* phone: a taste of the summary, nothing else. desktop: the lot. */}
                  {ins?.summary && (
                    <p className="text-sm text-muted-foreground line-clamp-2 lg:hidden">
                      {ins.summary.length > 100 ? `${ins.summary.slice(0, 100).trimEnd()}…` : ins.summary}
                    </p>
                  )}
                  {ins?.summary && (
                    <p className="hidden text-sm text-muted-foreground line-clamp-2 lg:block">{ins.summary}</p>
                  )}

                  {counts.length > 0 && (
                    <div className="hidden text-xs text-muted-foreground lg:block">{counts.join(" · ")}</div>
                  )}

                  <div className="hidden text-xs text-muted-foreground/70 truncate lg:block">
                    {doc.issued_date && `${formatDate(doc.issued_date)} · `}
                    {doc.file_name && `${doc.file_name} · `}
                    {t("added", { date: formatDate(doc.created_at) })}
                  </div>
                </div>
              </div>
              {/* Flush action panel: the buttons are the card's right edge, no
                  gutter around them. Each stretches to share the card's height,
                  so top and bottom sit exactly on the border. Desktop only. */}
              <div className="hidden w-40 shrink-0 flex-col divide-y border-l lg:flex [&>*]:min-h-11 [&>*]:flex-1 [&>*]:rounded-none [&>*]:border-0 [&>*]:justify-center">
                {doc.processing_status === "failed" && (
                  <span className={`inline-flex items-center justify-center text-xs font-medium ${statusBadgeColor("failed")}`}>
                    {t("failed")}
                  </span>
                )}

                {doc.processing_status === "failed" && <RetryButton docId={doc.id} />}

                {doc.verification_status === "extracted" && (
                  <Link
                    href={`/patients/${patientId}/documents/${doc.id}/verify`}
                    className="inline-flex items-center gap-2 text-sm font-medium bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20 transition-colors"
                  >
                    <ClipboardCheck className="h-4 w-4" />
                    {t("verify")}
                  </Link>
                )}

                <Link
                  href={`/patients/${patientId}/documents/${doc.id}`}
                  className="inline-flex items-center gap-2 text-sm font-medium bg-blue-500/10 text-blue-700 dark:text-blue-400 hover:bg-blue-500/20 transition-colors"
                >
                  <Eye className="h-4 w-4" />
                  {t("view")}
                </Link>

                <a
                  href={`/api/documents/${doc.id}/file`}
                  className="inline-flex items-center gap-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                >
                  <Download className="h-4 w-4" />
                  {t("download")}
                </a>

                <DeleteDocumentButton
                  docId={doc.id}
                  patientId={patientId}
                  stayOnList
                  className="bg-transparent text-destructive hover:bg-destructive/10 shadow-none"
                />
              </div>
             </div>

              {/* Phone: the actions appear under the card once it is tapped */}
              {open && (
                <div className="flex items-stretch divide-x border-t lg:hidden [&>*]:min-h-12 [&>*]:flex-1 [&>*]:justify-center [&>*]:rounded-none [&>*]:border-0">
                  {doc.processing_status === "failed" && <RetryButton docId={doc.id} />}

                  {doc.verification_status === "extracted" && (
                    <Link
                      href={`/patients/${patientId}/documents/${doc.id}/verify`}
                      aria-label={t("verify")}
                      className="inline-flex items-center bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    >
                      <ClipboardCheck className="h-5 w-5" />
                    </Link>
                  )}

                  <Link
                    href={`/patients/${patientId}/documents/${doc.id}`}
                    aria-label={t("view")}
                    className="inline-flex items-center bg-blue-500/10 text-blue-700 dark:text-blue-400"
                  >
                    <Eye className="h-5 w-5" />
                  </Link>

                  <a
                    href={`/api/documents/${doc.id}/file`}
                    aria-label={t("download")}
                    className="inline-flex items-center text-foreground"
                  >
                    <Download className="h-5 w-5" />
                  </a>

                  <DeleteDocumentButton
                    docId={doc.id}
                    patientId={patientId}
                    stayOnList
                    iconOnly
                    className="bg-transparent text-destructive shadow-none"
                  />
                </div>
              )}
            </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
