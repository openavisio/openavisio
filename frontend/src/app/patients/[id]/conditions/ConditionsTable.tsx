"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatDate, statusBadgeColor } from "@/lib/utils";
import { ConditionActions } from "./ConditionActions";
import { MergeConditionButton } from "./MergeConditionButton";
import { ConditionName } from "./ConditionName";

function sortedSources(sources: any[]) {
  return [...sources].sort((a: any, b: any) => (a.issued_date ?? "9999").localeCompare(b.issued_date ?? "9999"));
}

function Sources({ sources, patientId }: { sources: any[]; patientId: string }) {
  const t = useTranslations("Conditions");
  const dates = sources.map((s: any) => s.issued_date).filter(Boolean).sort();
  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap">
      <span>
        {t("documents", { count: sources.length })}
        {dates.length > 1 ? ` · ${formatDate(dates[0])} – ${formatDate(dates[dates.length - 1])}` : ""}
      </span>
      {/* native <details>, but the list is an absolutely positioned popover —
          expanding must not shove the table rows around */}
      <details className="relative">
        <summary
          className="flex cursor-pointer select-none items-center rounded p-0.5 text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden"
          style={{ listStyle: "none" }}
          title={t("showDocuments")}
        >
          <FileText className="h-3.5 w-3.5" />
        </summary>
        <ul className="absolute right-0 z-10 mt-1 w-64 space-y-1 rounded-md border bg-card p-2 shadow-md">
          {sortedSources(sources).map((s: any) => (
            <li key={s.document_reference_id} className="truncate">
              <a
                href={`/patients/${patientId}/documents/${s.document_reference_id}`}
                title={s.label || undefined}
                className="underline decoration-dotted underline-offset-2 hover:text-foreground"
              >
                {s.doc_type ? `${s.doc_type} · ` : ""}
                {s.issued_date ? `${formatDate(s.issued_date)} · ` : ""}
                {s.label || "Document"}
              </a>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function tSafe(t: any, key: string, raw: string | null | undefined) {
  if (!raw) return "—";
  try { return t(`${key}_${raw}`); } catch { return raw; }
}

export function ConditionsTable({ conditions, patientId }: { conditions: any[]; patientId: string }) {
  // Phone: the documents-list look — one card per condition, a tap reveals the
  // icon action bar under the card. Desktop keeps the table.
  const t = useTranslations("Conditions");
  const [revealed, setRevealed] = useState<string | null>(null);

  return (
    <>
      <div className="space-y-3 lg:hidden">
        {conditions.map((c: any) => {
          const open = revealed === c.id;
          return (
            <div
              key={c.id}
              className={`overflow-hidden rounded-xl border bg-card ${c.clinical_status === "inactive" ? "opacity-50" : ""}`}
            >
              <div className="p-4" onClick={() => setRevealed(open ? null : c.id)}>
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 text-sm font-medium"><ConditionName name={c.code_display} />{c.verification_status === "provisional" && (
                    <span className="ml-2 inline-block rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground">{t("suspected")}</span>
                  )}{c.note && <span className="block whitespace-pre-line text-xs font-normal text-muted-foreground">{c.note}</span>}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeColor(c.clinical_status)}`}>
                    {tSafe(t, "status", c.clinical_status)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {c.onset_date_time && <>{formatDate(c.onset_date_time)} · </>}
                  {c.severity && <span className="capitalize">{tSafe(t, "severity", c.severity)} · </span>}
                  {c.sources?.length ? t("documents", { count: c.sources.length }) : t("manual")}
                </div>
              </div>
              {/* full-width rows with a real touch height — a text link in xs font
                  is a target nobody hits on the first try */}
              {open && c.sources?.length > 0 && (
                <ul className="divide-y border-t">
                  {sortedSources(c.sources).map((s: any) => (
                    <li key={s.document_reference_id}>
                      <a
                        href={`/patients/${patientId}/documents/${s.document_reference_id}`}
                        className="flex min-h-11 items-center gap-2.5 px-4 py-2 text-sm active:bg-muted/50"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 truncate">
                          {s.doc_type && <span className="font-medium">{s.doc_type} · </span>}
                          {s.issued_date && <span className="text-muted-foreground">{formatDate(s.issued_date)} · </span>}
                          {s.label || "Document"}
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {open && (
                <ConditionActions
                  id={c.id}
                  status={c.clinical_status}
                  iconBar
                  extra={
                    <MergeConditionButton
                      id={c.id}
                      name={c.code_display}
                      candidates={conditions.filter((x: any) => x.id !== c.id).map((x: any) => ({ id: x.id, name: x.code_display }))}
                      iconBar
                    />
                  }
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="hidden overflow-hidden rounded-xl border bg-card lg:block">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("colCondition")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("colOnset")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("colSeverity")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("colStatus")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("colSource")}</th>
              <th className="w-px px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {conditions.map((c: any) => (
              <tr key={c.id} className={`hover:bg-muted/30 transition-colors ${c.clinical_status === "inactive" ? "opacity-50" : ""}`}>
                <td className="px-4 py-3 font-medium max-w-0 w-1/2"><ConditionName name={c.code_display} />{c.verification_status === "provisional" && (
                    <span className="ml-2 rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground">{t("suspected")}</span>
                  )}{c.note && <span className="block whitespace-pre-line text-xs font-normal text-muted-foreground">{c.note}</span>}</td>
                <td className="px-4 py-3 text-muted-foreground">{formatDate(c.onset_date_time)}</td>
                <td className="px-4 py-3 text-muted-foreground capitalize">{tSafe(t, "severity", c.severity)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadgeColor(c.clinical_status)}`}>
                    {tSafe(t, "status", c.clinical_status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs">
                  {c.sources?.length ? <Sources sources={c.sources} patientId={patientId} /> : t("manual")}
                </td>
                <td className="w-px whitespace-nowrap px-4 py-3">
                  <div className="flex items-center gap-2">
                    <MergeConditionButton
                      id={c.id}
                      name={c.code_display}
                      candidates={conditions.filter((x: any) => x.id !== c.id).map((x: any) => ({ id: x.id, name: x.code_display }))}
                    />
                    <ConditionActions id={c.id} status={c.clinical_status} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
