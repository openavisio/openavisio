"use client";

import { useState, useTransition } from "react";
import { Link2, Trash2, Plus, Eye } from "lucide-react";
import { useTranslations, useFormatter } from "next-intl";
import { addShareLinkDocumentsAction, revokeShareLinkAction } from "./share-link-actions";

type Doc = { id: string; file_name: string | null; description: string | null };

type LinkDoc = { document_id: string; file_name: string | null };

type ShareLink = {
  id: string;
  status: string; // active | revoked | expired
  expires_at: string;
  created_at: string;
  documents: LinkDoc[];
  handout: { variant: string } | null;
  access_count: number;
  last_accessed_at: string | null;
};

function statusClass(status: string) {
  if (status === "active") return "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300";
  return "bg-muted text-muted-foreground";
}

function LinkRow({ patientId, link, documents }: { patientId: string; link: ShareLink; documents: Doc[] }) {
  const t = useTranslations("ShareLinks");
  const f = useFormatter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  const inLink = new Set(link.documents.map((d) => d.document_id));
  const addable = documents.filter((d) => !inLink.has(d.id));

  function revoke() {
    setError("");
    startTransition(async () => {
      const r = await revokeShareLinkAction(patientId, link.id);
      if (r.error) setError(r.error);
    });
  }

  function addDocuments() {
    setError("");
    startTransition(async () => {
      const r = await addShareLinkDocumentsAction(patientId, link.id, selected);
      if (r.error) setError(r.error);
      else { setSelected([]); setAdding(false); }
    });
  }

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${statusClass(link.status)}`}>
              {t(`status_${link.status}` as any)}
            </span>
            <span className="text-sm text-muted-foreground">
              {link.documents.length} {t("documentsCount")}
              {link.handout && ` + ${t("withHandout")}`}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {link.status === "active"
              ? t("expiresAt", { date: f.dateTime(new Date(link.expires_at), { dateStyle: "medium" }) })
              : t("expiredOrRevoked")}
          </p>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Eye className="size-3" />
            {t("accessCount", { count: link.access_count })}
            {link.last_accessed_at &&
              ` · ${t("lastAccess", { date: f.dateTime(new Date(link.last_accessed_at), { dateStyle: "medium", timeStyle: "short" }) })}`}
          </p>
        </div>

        {link.status === "active" && (
          <button
            onClick={revoke}
            disabled={pending}
            className="inline-flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50"
          >
            <Trash2 className="size-3.5" /> {pending ? t("revoking") : t("revoke")}
          </button>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {link.status === "active" && addable.length > 0 && (
        adding ? (
          <div className="space-y-2 rounded-md border bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("addDocuments")}</p>
            <ul className="space-y-1 max-h-40 overflow-y-auto">
              {addable.map((d) => (
                <li key={d.id}>
                  <label className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted/50 cursor-pointer text-sm">
                    <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} className="size-4" />
                    <span className="truncate">{d.file_name || d.description || d.id}</span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <button
                onClick={addDocuments}
                disabled={pending || selected.length === 0}
                className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {pending ? t("adding") : t("addSelected")}
              </button>
              <button onClick={() => { setAdding(false); setSelected([]); }} className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
                {t("cancel")}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80"
          >
            <Plus className="size-3.5" /> {t("addDocuments")}
          </button>
        )
      )}
    </div>
  );
}

export function ShareLinksPanel({
  patientId,
  links,
  documents,
}: {
  patientId: string;
  links: ShareLink[];
  documents: Doc[];
}) {
  const t = useTranslations("ShareLinks");
  if (links.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm flex items-center gap-2">
        <Link2 className="size-4 text-muted-foreground" />
        {t("title")}
      </div>
      <div className="p-4 space-y-3">
        {links.map((link) => (
          <LinkRow key={link.id} patientId={patientId} link={link} documents={documents} />
        ))}
      </div>
    </div>
  );
}
