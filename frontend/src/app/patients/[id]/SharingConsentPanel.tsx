"use client";

import { useState, useTransition } from "react";
import { Share2, Check, X, Trash2, ShieldAlert, RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { consentShareAction, declineShareAction, revokeShareAction } from "./sharing-actions";
import { dataSetLabel } from "@/lib/data-set";

type OpenRequest = {
  id: string;
  name: string;
  description: string | null;
  identification_mode: string;
  expires_at: string | null;
  data_set?: string | null;
  data_set_since?: string | null;
  data_set_domain?: string | null;
};

type Row = { id: string; values: Record<string, unknown> };

type Doc = { id: string; file_name: string | null; description: string | null };

type Share = {
  id: string;
  sharing_purpose_id: string;
  status: string;
  purpose_name: string | null;
  document_file_name: string | null;
  consented_at: string;
  data_set?: string | null;
  row_count?: number | null;
  purpose_open?: boolean;
  identification_mode?: string | null;
};

// One line per row as it would leave, labels from the Development page (ADR 064)
function RowText({ v }: { v: Record<string, unknown> }) {
  const t = useTranslations("Sharing");
  const td = useTranslations("Development");
  const parts =
    "test" in v
      ? [v.test, v.outcome && td(`outcomes.${v.outcome}`), v.setting && td(`settings.${v.setting}`), v.reason]
      : [v.ability, v.works ? t("worksYes") : t("worksNo"), v.with_help ? t("withHelp") : t("alone"), v.place && td(`places.${v.place}`), v.note];
  return (
    <span className="min-w-0">
      <span className="text-muted-foreground tabular-nums">{String(v.date)}</span>{" "}
      <span className="break-words">{parts.filter(Boolean).map(String).join(" · ")}</span>
    </span>
  );
}

function DataSetPicker({
  patientId, purposeId, rows, anonymous, onDecline,
}: { patientId: string; purposeId: string; rows: Row[]; anonymous: boolean; onDecline?: () => void }) {
  const t = useTranslations("Sharing");
  const [selected, setSelected] = useState<string[]>(rows.map((r) => r.id));
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function share() {
    setError("");
    startTransition(async () => {
      const r = await consentShareAction(patientId, purposeId, selected, "record_ids");
      if (r.error) setError(r.error);
    });
  }

  return (
    <div className="space-y-3">
      <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-xs ${anonymous ? "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300" : "bg-muted text-muted-foreground"}`}>
        {anonymous ? <ShieldAlert className="size-4 shrink-0 mt-0.5" /> : <Share2 className="size-4 shrink-0 mt-0.5" />}
        <span>{anonymous ? t("dataSetAnonymous") : t("identifiedNote")} {t("dataSetNote")}</span>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("selectRows")}</p>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noRows")}</p>
        ) : (
          <ul className="space-y-1 max-h-72 overflow-y-auto">
            {rows.map((r) => (
              <li key={r.id}>
                <label className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 cursor-pointer text-sm">
                  <input type="checkbox" checked={selected.includes(r.id)} onChange={() => toggle(r.id)} className="size-4 mt-0.5 shrink-0" />
                  <RowText v={r.values} />
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {rows.length > 0 && (
          <button
            onClick={share}
            disabled={pending || selected.length === 0}
            className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            <Check className="size-3.5" />
            {pending ? t("sharing") : t("shareSelected")}
          </button>
        )}
        {onDecline && (
          <button
            onClick={onDecline}
            disabled={pending}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <X className="size-3.5" />
            {t("decline")}
          </button>
        )}
      </div>
    </div>
  );
}

function RequestCard({ patientId, request, documents, rows }: { patientId: string; request: OpenRequest; documents: Doc[]; rows?: Row[] }) {
  const t = useTranslations("Sharing");
  const td = useTranslations("Development");
  const locale = useLocale();
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const anonymous = request.identification_mode === "anonymous";

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function share() {
    setError("");
    startTransition(async () => {
      const r = await consentShareAction(patientId, request.id, selected, "document_ids");
      if (r.error) setError(r.error);
      else setSelected([]);
    });
  }

  function decline() {
    setError("");
    startTransition(async () => {
      const r = await declineShareAction(patientId, request.id);
      if (r.error) setError(r.error);
    });
  }

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div>
        <p className="font-medium text-sm">{request.name}</p>
        {request.data_set && (
          <p className="text-sm text-muted-foreground">{t("asksFor")}: {dataSetLabel(t, td, request, locale)}</p>
        )}
        {request.description && (
          <p className="text-sm text-muted-foreground">{request.data_set ? request.description : `${t("asksFor")}: ${request.description}`}</p>
        )}
      </div>

      {request.data_set ? (
        <DataSetPicker patientId={patientId} purposeId={request.id} rows={rows ?? []} anonymous={anonymous} onDecline={decline} />
      ) : (<>

      <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-xs ${anonymous ? "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300" : "bg-muted text-muted-foreground"}`}>
        {anonymous ? <ShieldAlert className="size-4 shrink-0 mt-0.5" /> : <Share2 className="size-4 shrink-0 mt-0.5" />}
        <span>{anonymous ? t("anonymousWarning") : t("identifiedNote")}</span>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("selectFiles")}</p>
        {documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noDocuments")}</p>
        ) : (
          <ul className="space-y-1 max-h-56 overflow-y-auto">
            {documents.map((d) => (
              <li key={d.id}>
                <label className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 cursor-pointer text-sm">
                  <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} className="size-4" />
                  <span className="truncate">{d.file_name || d.description || d.id}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={share}
          disabled={pending || selected.length === 0}
          className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          <Check className="size-3.5" />
          {pending ? t("sharing") : t("shareSelected")}
        </button>
        <button
          onClick={decline}
          disabled={pending}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          <X className="size-3.5" />
          {t("decline")}
        </button>
      </div>
      </>)}
    </div>
  );
}

function ShareRow({ patientId, share, rows, onShareAgain }: { patientId: string; share: Share; rows?: Row[]; onShareAgain: () => void }) {
  const t = useTranslations("Sharing");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const canShareAgain = share.data_set && share.status === "active" && share.purpose_open && rows;

  function revoke() {
    setError("");
    startTransition(async () => {
      const r = await revokeShareAction(patientId, share.id);
      if (r.error) setError(r.error);
    });
  }

  return (
    <>
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-2 text-sm">
        {share.data_set ? `${t(`DataSet_${share.data_set}`)}, ${t("rows", { n: share.row_count ?? 0 })}` : share.document_file_name || "—"}
      </td>
      <td className="px-4 py-2 text-sm text-muted-foreground">{share.purpose_name || "—"}</td>
      <td className="px-4 py-2">
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${share.status === "active" ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300" : "bg-muted text-muted-foreground"}`}>
          {t(`status_${share.status}`)}
        </span>
      </td>
      <td className="px-4 py-2 text-right space-x-3 whitespace-nowrap">
        {canShareAgain && (
          <button onClick={onShareAgain} className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80">
            <RefreshCw className="size-3.5" /> {t("shareAgain")}
          </button>
        )}
        {share.status === "active" && (
          <button onClick={revoke} disabled={pending} className="inline-flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50">
            <Trash2 className="size-3.5" /> {pending ? t("revoking") : t("revoke")}
          </button>
        )}
        {error && <p className="text-xs text-destructive mt-1">{error}</p>}
      </td>
    </tr>
    </>
  );
}

export function SharingConsentPanel({
  patientId,
  openRequests,
  shares,
  documents,
  rowsByPurpose,
}: {
  patientId: string;
  openRequests: OpenRequest[];
  shares: Share[];
  documents: Doc[];
  rowsByPurpose: Record<string, Row[]>;
}) {
  const t = useTranslations("Sharing");
  // the picker sits below the table, which scrolls sideways on a phone
  const [againId, setAgainId] = useState<string | null>(null);
  const again = shares.find((s) => s.id === againId);

  if (openRequests.length === 0 && shares.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm flex items-center gap-2">
        <Share2 className="size-4 text-muted-foreground" />
        {t("title")}
      </div>
      <div className="p-4 space-y-4">
        {openRequests.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("openRequests")}</p>
            {openRequests.map((r) => (
              <RequestCard key={r.id} patientId={patientId} request={r} documents={documents} rows={rowsByPurpose[r.id]} />
            ))}
          </div>
        )}

        {shares.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("myShares")}</p>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/30">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("file")}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("purpose")}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{t("statusLabel")}</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {shares.map((s) => (
                    <ShareRow key={s.id} patientId={patientId} share={s} rows={rowsByPurpose[s.sharing_purpose_id]}
                      onShareAgain={() => setAgainId(againId === s.id ? null : s.id)} />
                  ))}
                </tbody>
              </table>
            </div>
            {again && rowsByPurpose[again.sharing_purpose_id] && (
              <div className="rounded-lg border p-4 space-y-2">
                <p className="font-medium text-sm">{again.purpose_name}</p>
                <DataSetPicker key={again.id} patientId={patientId} purposeId={again.sharing_purpose_id}
                  rows={rowsByPurpose[again.sharing_purpose_id]} anonymous={again.identification_mode === "anonymous"} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
