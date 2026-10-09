"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Merge } from "lucide-react";
import { mergeCondition } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export type MergeCandidate = { id: string; name: string };

// Merge two conditions (#159): pick the partner, pick the surviving name,
// confirm. Winner keeps name/severity/status, earliest onset survives, sources
// and notes are unioned. No automatic unmerge — the dialog says so.
export function MergeConditionButton({ id, name, candidates, iconBar = false }: {
  id: string;
  name: string;
  candidates: MergeCandidate[];
  iconBar?: boolean;
}) {
  const t = useTranslations("Conditions");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [partnerId, setPartnerId] = useState<string | null>(null);
  const [keepName, setKeepName] = useState<string>(name);

  const partner = candidates.find((c) => c.id === partnerId) || null;

  function submit() {
    if (!partner) return;
    // the row whose name survives is the winner and keeps its clinical fields
    const winner = keepName === name ? id : partner.id;
    const loser = winner === id ? partner.id : id;
    startTransition(async () => {
      await mergeCondition(winner, loser);
      setOpen(false);
      router.refresh();
    });
  }

  if (candidates.length === 0) return null;

  return (
    <>
      {iconBar ? (
        <button
          onClick={(e) => { e.stopPropagation(); setOpen(true); }}
          aria-label={t("merge")}
          className="inline-flex items-center text-foreground"
        >
          <Merge className="h-5 w-5" />
        </button>
      ) : (
        <button
          onClick={() => setOpen(true)}
          title={t("merge")}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/70 transition-colors"
        >
          <Merge className="h-3.5 w-3.5" />
          {t("merge")}
        </button>
      )}

      <Dialog open={open} onOpenChange={(v) => !pending && (setOpen(v), setPartnerId(null), setKeepName(name))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("mergeTitle", { name })}</DialogTitle>
            <DialogDescription>{t("mergeHint")}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 px-6">
            <div>
              <p className="mb-1.5 text-sm font-medium">{t("mergeWith")}</p>
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border p-2">
                {candidates.map((c) => (
                  <label key={c.id} className="flex min-h-9 cursor-pointer items-center gap-2 rounded px-2 text-sm hover:bg-muted/50">
                    <input
                      type="radio"
                      name="merge-partner"
                      checked={partnerId === c.id}
                      onChange={() => setPartnerId(c.id)}
                    />
                    <span className="min-w-0 truncate">{c.name}</span>
                  </label>
                ))}
              </div>
            </div>

            {partner && (
              <div>
                <p className="mb-1.5 text-sm font-medium">{t("keepName")}</p>
                {[name, partner.name].map((n) => (
                  <label key={n} className="flex min-h-9 cursor-pointer items-center gap-2 rounded px-2 text-sm hover:bg-muted/50">
                    <input
                      type="radio"
                      name="merge-name"
                      checked={keepName === n}
                      onChange={() => setKeepName(n)}
                    />
                    <span className="min-w-0 truncate">{n}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={pending}>
              {t("cancel")}
            </Button>
            <Button size="sm" disabled={pending || !partner} onClick={submit}>
              {pending ? t("merging") : t("merge")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
