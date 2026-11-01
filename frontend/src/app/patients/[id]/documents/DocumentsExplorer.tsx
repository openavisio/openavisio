"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/hooks/use-mobile";
import { useLocale, useTranslations } from "next-intl";
import {
  FileText, ClipboardCheck, Eye, Search, X, Download, Star, Loader2,
  LayoutGrid, LayoutList, Table2,
} from "lucide-react";
import { getDocumentNovelty, getDocuments, type S } from "@/lib/api";
import { formatDate, statusBadgeColor } from "@/lib/utils";
import { RetryButton } from "./UploadPanel";
import { FavoriteButton } from "./FavoriteButton";
import { DeleteDocumentButton } from "./[docId]/DeleteDocumentButton";

type Doc = S<"DocumentDto">;

const RANGES = { "3m": 91, "12m": 365, all: Infinity } as const;
type RangeKey = keyof typeof RANGES;

// Every non-terminal pipeline status set by backend/app/workers/pipeline.py.
// Miss one and the poll stops mid-run, leaving the row stuck until a manual
// reload. Terminal: completed, failed.
const IN_PROGRESS = new Set([
  "pending", "ocr_processing", "ocr_done", "classifying", "classified", "extracting", "extracted", "embedding",
]);

// One colour per Correspondent, so "the fifth SPZ report" is visible at a glance
const CORRESPONDENT_COLORS = [
  { dot: "bg-sky-500", border: "border-l-sky-500", top: "border-t-sky-500" },
  { dot: "bg-emerald-500", border: "border-l-emerald-500", top: "border-t-emerald-500" },
  { dot: "bg-violet-500", border: "border-l-violet-500", top: "border-t-violet-500" },
  { dot: "bg-amber-500", border: "border-l-amber-500", top: "border-t-amber-500" },
  { dot: "bg-rose-500", border: "border-l-rose-500", top: "border-t-rose-500" },
  { dot: "bg-teal-500", border: "border-l-teal-500", top: "border-t-teal-500" },
  { dot: "bg-orange-500", border: "border-l-orange-500", top: "border-t-orange-500" },
  { dot: "bg-indigo-500", border: "border-l-indigo-500", top: "border-t-indigo-500" },
];
type CorrespondentColor = (typeof CORRESPONDENT_COLORS)[number];
const NO_CORRESPONDENT: CorrespondentColor = { dot: "bg-muted-foreground/40", border: "border-l-border", top: "border-t-border" };

// The letterhead name varies from letter to letter: a department after the comma,
// "– Pflegekasse", the legal form. Dropping those joins most variants of one Correspondent.
function correspondentOf(doc: Doc): string {
  return simplifyCorrespondent(doc.correspondent?.name || doc.detected_provider || doc.insights?.provider || "");
}
function simplifyCorrespondent(raw: string): string {
  return raw.split(",")[0].split(/\s[–-]\s/)[0].replace(/\s+(gGmbH|GmbH|gAG|AG|e\.\s?V\.|mbH)$/i, "").trim();
}

// Colours by how many letters a Correspondent has, so the most frequent eight never share one.
function correspondentColors(docs: Doc[]): (d: Doc) => CorrespondentColor {
  const count = new Map<string, number>();
  docs.forEach((d) => { const s = correspondentOf(d); if (s) count.set(s, (count.get(s) ?? 0) + 1); });
  const rank = new Map([...count.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([s], i) => [s, i]));
  return (d) => {
    const i = rank.get(correspondentOf(d));
    return i === undefined ? NO_CORRESPONDENT : CORRESPONDENT_COLORS[i % CORRESPONDENT_COLORS.length];
  };
}
export type Novelty = {
  new: { diagnoses: number; medications: number; observations: number };
  known: number;
  repeats: { id: string; label: string | null; issued_date: string | null } | null;
};
// A per-viewer choice kept in this browser; the first value is the default.
const remembered = new Set<() => void>();
function subscribeRemembered(cb: () => void) {
  remembered.add(cb);
  window.addEventListener("storage", cb);
  return () => { remembered.delete(cb); window.removeEventListener("storage", cb); };
}
function readRemembered(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function useRemembered<T extends string>(key: string, values: readonly T[]): [T, (v: T) => void] {
  const stored = useSyncExternalStore(subscribeRemembered, () => readRemembered(key), () => null);
  const value = values.includes(stored as T) ? (stored as T) : values[0];
  const set = (v: T) => {
    try { localStorage.setItem(key, v); } catch {}
    remembered.forEach((cb) => cb());
  };
  return [value, set];
}

function NoveltyLine({ n }: { n?: Novelty | null }) {
  const t = useTranslations("DocumentsPage");
  if (n === undefined) return null;
  // null: still loading; a bar where the line will be, not a skeleton for the whole card
  if (n === null) return <span className="block h-3 w-40 animate-pulse rounded bg-muted" aria-hidden />;
  const parts = [
    n.new.diagnoses && t("newDiagnoses", { count: n.new.diagnoses }),
    n.new.medications && t("newMedications", { count: n.new.medications }),
    n.new.observations && t("newObservations", { count: n.new.observations }),
  ].filter(Boolean);
  const repeats = n.repeats && t("repeats", {
    label: simplifyCorrespondent(n.repeats.label ?? "") || "?", date: n.repeats.issued_date ? formatDate(n.repeats.issued_date) : "",
  });
  if (!parts.length && !n.known) return null;
  return (
    <p className="text-xs">
      {parts.length ? (
        <span className="font-medium text-emerald-700 dark:text-emerald-400">{t("newPrefix")} {parts.join(", ")}</span>
      ) : (
        <span className="font-medium text-muted-foreground">{t("nothingNew")}</span>
      )}
      {repeats && <span className="text-muted-foreground">{" · "}{repeats}</span>}
    </p>
  );
}

// A caregiver-readable heading. The file name is often a scanner artefact
// ("img20240405_08273634.pdf"), so it is the last resort, not the first.
function docTitle(doc: Doc, t: (k: string) => string, tc: { (k: string): string; has(k: string): boolean }): string {
  if (doc.type) return doc.type;
  if (doc.document_classification && tc.has(`class_${doc.document_classification}`)) {
    return tc(`class_${doc.document_classification}`);
  }
  return doc.description || doc.file_name || t("unnamed");
}

// The pipeline in order. A bare "extracting…" says nothing about how far along
// a document is; four dots and a spinner do, and they sit in the card body
// rather than wedged between the buttons.
const STAGES = ["ocr", "classification", "extraction", "embedding"];

function PipelineProgress({ stage, label }: { stage: string | null; label: string }) {
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
  // loaded after the list: it waits on the model's grouping, the list must not
  const [novelty, setNovelty] = useState<Record<string, Novelty> | null>(null);
  useEffect(() => {
    getDocumentNovelty(patientId).then(setNovelty).catch(() => setNovelty({}));
  }, [patientId]);
  const [chosenView, setView] = useRemembered("docs.view", ["cards", "table", "preview"] as const);
  const [groupBy, setGroupBy] = useRemembered("docs.groupBy", ["month", "correspondent"] as const);
  const router = useRouter();
  const isMobile = useIsMobile();
  // a table squeezed to a phone's width helps nobody; there it is cards or preview
  const view = isMobile && chosenView === "table" ? "cards" : chosenView;
  const [searching, setSearching] = useState(false);
  const qRef = useRef(q);
  useEffect(() => { qRef.current = q; }, [q]);

  // server refresh (upload finished → router.refresh) replaces the base list
  const [base, setBase] = useState(initialDocuments);
  if (base !== initialDocuments) {
    setBase(initialDocuments);
    setDocs(initialDocuments);
  }

  // content search: debounced round-trip to the backend `q` filter
  useEffect(() => {
    const trimmed = q.trim();
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

  const [now] = useState(() => Date.now());
  const cutoff = now - RANGES[range] * 86_400_000;
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
  const colorOf = correspondentColors(docs);
  const sorted = [...filtered].sort((a, b) => docDate(b, sortBy).getTime() - docDate(a, sortBy).getTime());
  if (groupBy === "correspondent") {
    const byCorrespondent = new Map<string, Doc[]>();
    sorted.forEach((d) => byCorrespondent.set(correspondentOf(d), [...(byCorrespondent.get(correspondentOf(d)) ?? []), d]));
    [...byCorrespondent.entries()]
      .sort((a, b) => b[1].length - a[1].length)
      .forEach(([name, list]) => groups.push({ label: `${name || t("unknownCorrespondent")} (${list.length})`, docs: list }));
  } else {
    // by letter date, an undated letter would sink into its upload month and be lost there
    const undated = sortBy === "doc" ? sorted.filter((d) => !d.issued_date) : [];
    if (undated.length) groups.push({ label: `${t("noDate")} (${undated.length})`, docs: undated });
    sorted.filter((d) => !undated.includes(d)).forEach((d) => {
      const label = monthFmt.format(docDate(d, sortBy));
      const last = groups[groups.length - 1];
      if (last?.label === label) last.docs.push(d);
      else groups.push({ label, docs: [d] });
    });
  }

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
            onChange={(e) => { setQ(e.target.value); setSearching(true); }}
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
        <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex items-center rounded-md border border-border p-0.5">
          {(["month", "correspondent"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setGroupBy(k)}
              className={`px-2 py-0.5 rounded font-medium transition-colors ${
                groupBy === k ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t(k === "month" ? "groupByMonth" : "groupByCorrespondent")}
            </button>
          ))}
        </div>
        <div className="inline-flex items-center rounded-md border border-border p-0.5">
          {([["cards", LayoutList], ["table", Table2], ["preview", LayoutGrid]] as const).map(([k, Icon]) => (
            <button
              key={k}
              onClick={() => setView(k)}
              title={t(`view_${k}`)}
              aria-label={t(`view_${k}`)}
              // a segment of the switch, as tall as its text neighbours, not a 44px touch button
              className={`min-h-0 min-w-0 px-2 py-1 rounded transition-colors ${k === "table" ? "hidden md:block" : ""} ${
                view === k ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="size-3.5" />
            </button>
          ))}
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
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {docs.length === 0 ? t("noDocuments") : t("noMatches")}
        </div>
      ) : (
        // the month tables scroll sideways together on a phone, not each on its own
        <div className={view === "table" ? "-mx-1 overflow-x-auto px-1" : ""}>
        <div className={`space-y-4 ${view === "table" ? "min-w-[42rem] md:min-w-[62rem]" : ""}`}>
          {groups.map((group) => (
            <div key={group.label} className="space-y-3">
              <div className="flex items-center gap-3 pt-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground shrink-0">
                  {group.label}
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>
              {view === "table" && <DocTable docs={group.docs} patientId={patientId} novelty={novelty} colorOf={colorOf} title={(d) => docTitle(d, t, tc)} />}
              {view === "preview" && <DocGrid docs={group.docs} patientId={patientId} novelty={novelty} colorOf={colorOf} title={(d) => docTitle(d, t, tc)} />}
              {view === "cards" && group.docs.map((doc) => {
                const ins = doc.insights;
                const issuer = doc.detected_provider || ins?.provider || doc.correspondent?.name;
                const counts = [
                  ins?.observations && t("countObservations", { count: ins.observations }),
                  ins?.medications && t("countMedications", { count: ins.medications }),
                  ins?.diagnoses && t("countDiagnoses", { count: ins.diagnoses }),
                  ins?.recommendations && t("countRecommendations", { count: ins.recommendations }),
                ].filter(Boolean);
                return (
            <div key={doc.id} className={`overflow-hidden rounded-xl border border-l-4 bg-card ${colorOf(doc).border}`}>
             <div className="flex items-stretch">
              {/* On a phone one tap opens the document; download and favourite live there */}
              <div
                onClick={isMobile ? () => router.push(`/patients/${patientId}/documents/${doc.id}`) : undefined}
                className="min-w-0 flex-1"
              >
                {/* the Correspondent is how a letter is recognised; kind and date stand quietly under it */}
                <div className="flex items-start gap-2 border-b bg-muted/40 px-4 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold" title={issuer || undefined}>{correspondentOf(doc) || t("unknownCorrespondent")}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {[docTitle(doc, t, tc), doc.issued_date ? formatDate(doc.issued_date) : t("noDate")].join(" · ")}
                    </p>
                  </div>
                  {!isMobile && (
                    <FavoriteButton docId={doc.id} patientId={patientId} initial={!!doc.is_favorite} />
                  )}
                </div>
                <div className="min-w-0 space-y-1.5 p-4">

                  {IN_PROGRESS.has(doc.processing_status) && (
                    <PipelineProgress stage={doc.pipeline_stage} label={
                      doc.pipeline_stage ? t(`stage_${doc.pipeline_stage}`) : t("processing")
                    } />
                  )}

                  {/* a text hit shows where the word stands, in place of the summary (ADR 057) */}
                  {doc.snippet && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {doc.snippet[0]}<mark className="rounded bg-amber-500/20 px-0.5 text-foreground">{doc.snippet[1]}</mark>{doc.snippet[2]}
                    </p>
                  )}

                  {/* phone: a taste of the summary, nothing else. desktop: the lot. */}
                  {!doc.snippet && ins?.summary && (
                    <p className="text-sm text-muted-foreground line-clamp-2 lg:hidden">
                      {ins.summary.length > 100 ? `${ins.summary.slice(0, 100).trimEnd()}…` : ins.summary}
                    </p>
                  )}
                  {!doc.snippet && ins?.summary && (
                    <p className="hidden text-sm text-muted-foreground line-clamp-2 lg:block">{ins.summary}</p>
                  )}

                  {novelty === null ? <NoveltyLine n={null} /> : novelty[doc.id] ? <NoveltyLine n={novelty[doc.id]} /> : counts.length > 0 && (
                    <div className="hidden text-xs text-muted-foreground lg:block">{counts.join(" · ")}</div>
                  )}

                  {/* phone: a failed letter can be retried right here */}
                  {doc.processing_status === "failed" && (
                    <div className="lg:hidden" onClick={(e) => e.stopPropagation()}><RetryButton docId={doc.id} /></div>
                  )}

                  <div className="hidden text-xs text-muted-foreground/70 truncate lg:block">
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
                  className="gap-2 bg-transparent text-sm font-medium text-destructive shadow-none hover:bg-destructive/10"
                />
              </div>
             </div>
             {/* phone: the same action bar as under a preview tile */}
             <div className="border-t lg:hidden"><DocActions doc={doc} patientId={patientId} spread /></div>
            </div>
                );
              })}
            </div>
          ))}
        </div>
        </div>
      )}
    </div>
  );
}

function DocTable({ docs, patientId, novelty, colorOf, title }: {
  docs: Doc[]; patientId: string; novelty: Record<string, Novelty> | null;
  colorOf: (d: Doc) => CorrespondentColor; title: (d: Doc) => string;
}) {
  const router = useRouter();
  const t = useTranslations("DocumentsPage");
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      {/* one table per month: fixed columns keep them aligned with each other */}
      {/* every column a fixed width: a share of what is left squeezed "what is new" to nothing;
          on a phone kind and status give way; the minimum width sits on the shared scroll area */}
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-24" />
          <col className="w-44" />
          <col className="hidden w-36 md:table-column" />
          <col className="w-64" />
          <col className="hidden w-32 md:table-column" />
          <col className="w-40" />
        </colgroup>
        <thead className="text-left text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="px-3 py-2 font-medium">{t("colDate")}</th>
            <th className="px-3 py-2 font-medium">{t("colCorrespondent")}</th>
            <th className="hidden px-3 py-2 font-medium md:table-cell">{t("colKind")}</th>
            <th className="px-3 py-2 font-medium">{t("colNew")}</th>
            <th className="hidden px-3 py-2 font-medium md:table-cell">{t("colStatus")}</th>
            <th className="px-3 py-2"><span className="sr-only">{t("colActions")}</span></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr
              key={d.id}
              onClick={() => router.push(`/patients/${patientId}/documents/${d.id}`)}
              className="cursor-pointer border-b transition-colors last:border-0 hover:bg-primary/5"
            >
              <td className="whitespace-nowrap px-3 py-2">{d.issued_date ? formatDate(d.issued_date) : "—"}</td>
              <td className="px-3 py-2">
                <span className="flex min-w-0 items-center gap-2" title={correspondentOf(d) || undefined}>
                  <span className={`size-2.5 shrink-0 rounded-full ${colorOf(d).dot}`} />
                  <span className="truncate">{correspondentOf(d) || "—"}</span>
                </span>
              </td>
              <td className="hidden truncate px-3 py-2 md:table-cell" title={title(d)}>
                <Link href={`/patients/${patientId}/documents/${d.id}`} className="hover:underline">{title(d)}</Link>
              </td>
              <td className="overflow-hidden px-3 py-2"><NoveltyLine n={novelty === null ? null : novelty[d.id]} /></td>
              <td className="hidden px-3 py-2 text-xs leading-tight text-muted-foreground md:table-cell">
                {d.processing_status === "failed" ? t("failed")
                  : d.verification_status !== "extracted" ? ""
                  : !d.open_diagnoses && d.insights?.diagnoses ? t("diagnosesDone") : t("unverified")}
              </td>
              <td className="px-2 py-1"><DocActions doc={d} patientId={patientId} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// first page small for a PDF, the picture itself for an image, nothing for the rest
function preview(d: Doc): string | null {
  if (d.content_type === "application/pdf") return `/api/documents/${d.id}/pages/0?width=320`;
  if (d.content_type?.startsWith("image/")) return `/api/documents/${d.id}/file`;
  return null;
}

function DocGrid({ docs, patientId, novelty, colorOf, title }: {
  docs: Doc[]; patientId: string; novelty: Record<string, Novelty> | null;
  colorOf: (d: Doc) => CorrespondentColor; title: (d: Doc) => string;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {docs.map((d) => (
        <div key={d.id} className={`flex flex-col overflow-hidden rounded-xl border border-t-4 bg-card hover:shadow-md ${colorOf(d).top}`}>
        <Link href={`/patients/${patientId}/documents/${d.id}`} className="block flex-1">
          {preview(d) ? (
            // eslint-disable-next-line @next/next/no-img-element -- an authenticated route, not a static asset
            <img src={preview(d)!} alt="" loading="lazy" className="aspect-[3/4] w-full border-b bg-muted object-cover object-top" />
          ) : (
            <div className="flex aspect-[3/4] w-full items-center justify-center border-b bg-muted text-muted-foreground">
              <FileText className="size-8" />
            </div>
          )}
          <div className="space-y-1 p-2">
            <p className="truncate text-sm font-semibold">{correspondentOf(d) || title(d)}</p>
            <p className="truncate text-xs text-muted-foreground">
              {[correspondentOf(d) && title(d), d.issued_date && formatDate(d.issued_date)].filter(Boolean).join(" · ")}
            </p>
            <NoveltyLine n={novelty === null ? null : novelty[d.id]} />
          </div>
        </Link>
        <div className="border-t"><DocActions doc={d} patientId={patientId} spread /></div>
        </div>
      ))}
    </div>
  );
}

// Prüfen, ansehen, herunterladen, löschen as icons: in the table a row at the end,
// under a preview tile a bar of equal cells tinted like the cards' action column
function DocActions({ doc, patientId, spread }: { doc: Doc; patientId: string; spread?: boolean }) {
  const t = useTranslations("DocumentsPage");
  const cell = spread
    ? "inline-flex h-9 items-center justify-center transition-colors"
    : "inline-flex size-8 items-center justify-center rounded-md transition-colors";
  return (
    <div
      className={spread ? "grid auto-cols-fr grid-flow-col divide-x" : "flex items-center justify-end gap-0.5"}
      onClick={(e) => e.stopPropagation()}
    >
      {doc.verification_status === "extracted" && (
        <Link href={`/patients/${patientId}/documents/${doc.id}/verify`} title={t("verify")} aria-label={t("verify")}
              className={`${cell} ${spread ? "bg-amber-500/10" : ""} text-amber-700 hover:bg-amber-500/20 dark:text-amber-400`}>
          <ClipboardCheck className="size-4" />
        </Link>
      )}
      <Link href={`/patients/${patientId}/documents/${doc.id}`} title={t("view")} aria-label={t("view")}
            className={`${cell} ${spread ? "bg-blue-500/10" : ""} text-blue-700 hover:bg-blue-500/20 dark:text-blue-400`}>
        <Eye className="size-4" />
      </Link>
      <a href={`/api/documents/${doc.id}/file`} title={t("download")} aria-label={t("download")} className={`${cell} hover:bg-muted`}>
        <Download className="size-4" />
      </a>
      <DeleteDocumentButton docId={doc.id} patientId={patientId} stayOnList iconOnly
        className={`${spread ? "h-9 w-full rounded-none" : "size-8"} bg-transparent p-0 text-destructive shadow-none hover:bg-destructive/10 [&_svg]:size-4`} />
    </div>
  );
}
