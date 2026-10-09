"use client";

import { useState, useTransition } from "react";
import { Share2, Check, X, Trash2, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { consentShareAction, declineShareAction, revokeShareAction } from "./sharing-actions";

type OpenRequest = {
  id: string;
  name: string;
  description: string | null;
  identification_mode: string;
  expires_at: string | null;
};

type Doc = { id: string; file_name: string | null; description: string | null };

type Share = {
  id: string;
  status: string;
  purpose_name: string | null;
  document_file_name: string | null;
  consented_at: string;
};

function RequestCard({ patientId, request, documents }: { patientId: string; request: OpenRequest; documents: Doc[] }) {
  const t = useTranslations("Sharing");
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
      const r = await consentShareAction(patientId, request.id, selected);
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
        {request.description && (
          <p className="text-sm text-muted-foreground">{t("asksFor")}: {request.description}</p>
        )}
      </div>

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
    </div>
  );
}

function ShareRow({ patientId, share }: { patientId: string; share: Share }) {
  const t = useTranslations("Sharing");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function revoke() {
    setError("");
    startTransition(async () => {
      const r = await revokeShareAction(patientId, share.id);
      if (r.error) setError(r.error);
    });
  }

  return (
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-2 text-sm">{share.document_file_name || "—"}</td>
      <td className="px-4 py-2 text-sm text-muted-foreground">{share.purpose_name || "—"}</td>
      <td className="px-4 py-2">
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${share.status === "active" ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300" : "bg-muted text-muted-foreground"}`}>
          {t(`status_${share.status}` as any)}
        </span>
      </td>
      <td className="px-4 py-2 text-right">
        {share.status === "active" && (
          <button onClick={revoke} disabled={pending} className="inline-flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50">
            <Trash2 className="size-3.5" /> {pending ? t("revoking") : t("revoke")}
          </button>
        )}
        {error && <p className="text-xs text-destructive mt-1">{error}</p>}
      </td>
    </tr>
  );
}

export function SharingConsentPanel({
  patientId,
  openRequests,
  shares,
  documents,
}: {
  patientId: string;
  openRequests: OpenRequest[];
  shares: Share[];
  documents: Doc[];
}) {
  const t = useTranslations("Sharing");

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
              <RequestCard key={r.id} patientId={patientId} request={r} documents={documents} />
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
                    <ShareRow key={s.id} patientId={patientId} share={s} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
