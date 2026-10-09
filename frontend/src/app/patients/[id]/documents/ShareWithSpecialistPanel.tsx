"use client";

import { useState, useTransition } from "react";
import { Link2, Check, Copy, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { createShareLinkAction } from "../share-link-actions";

type Doc = { id: string; file_name: string | null; description: string | null; type: string | null };

const EXPIRY_OPTIONS = [7, 30, 90];

export function ShareWithSpecialistPanel({ patientId, documents }: { patientId: string; documents: Doc[] }) {
  const t = useTranslations("ShareLinks");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [expiry, setExpiry] = useState(30);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function create() {
    setError("");
    startTransition(async () => {
      const r = await createShareLinkAction(patientId, selected, expiry);
      if (r.error) setError(r.error);
      else {
        setCreatedUrl(r.url ?? "");
        setSelected([]);
      }
    });
  }

  async function copy() {
    if (!createdUrl) return;
    await navigator.clipboard.writeText(createdUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (documents.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card mb-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium hover:bg-muted/40 transition-colors"
      >
        <Link2 className="size-4 text-muted-foreground" />
        {t("shareWithSpecialist")}
      </button>

      {open && (
        <div className="border-t p-4 space-y-4">
          {createdUrl !== null ? (
            <div className="space-y-3">
              <div className="flex items-start gap-2 rounded-md bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 px-3 py-2 text-xs">
                <ShieldAlert className="size-4 shrink-0 mt-0.5" />
                <span>{t("copyOnceWarning")}</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={createdUrl}
                  className="flex-1 rounded-lg border bg-muted px-3 py-2 text-sm font-mono"
                  onFocus={(e) => e.currentTarget.select()}
                />
                <button
                  onClick={copy}
                  className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90"
                >
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                  {copied ? t("copied") : t("copy")}
                </button>
              </div>
              <button
                onClick={() => { setCreatedUrl(null); setOpen(false); }}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                {t("done")}
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">{t("createHint")}</p>
              {error && <p className="text-sm text-destructive">{error}</p>}

              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("selectDocuments")}</p>
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
              </div>

              <div className="flex items-center gap-3">
                <label className="text-sm text-muted-foreground">{t("expiry")}</label>
                <select
                  value={expiry}
                  onChange={(e) => setExpiry(Number(e.target.value))}
                  className="rounded-lg border bg-background px-2 py-1.5 text-sm"
                >
                  {EXPIRY_OPTIONS.map((d) => (
                    <option key={d} value={d}>{t("days", { count: d })}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={create}
                disabled={pending || selected.length === 0}
                className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                <Link2 className="size-4" />
                {pending ? t("creating") : t("createLink")}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
