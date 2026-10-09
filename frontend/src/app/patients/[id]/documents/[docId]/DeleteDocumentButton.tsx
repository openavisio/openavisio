"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { deleteDocumentAction } from "./actions";

export function DeleteDocumentButton({
  docId,
  patientId,
  className,
  stayOnList,
  iconOnly,
}: {
  docId: string;
  patientId: string;
  className?: string;
  iconOnly?: boolean;
  // from the list the document just disappears; from the detail page there is
  // no page left to stay on, so we navigate back
  stayOnList?: boolean;
}) {
  const t = useTranslations("DocumentsPage");
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  function handleDelete() {
    setError(null);
    startTransition(async () => {
      const result = await deleteDocumentAction(docId, patientId);
      if (result.error) {
        setError(result.error);
        return;
      }
      setOpen(false);
      if (stayOnList) router.refresh();
      else router.push(`/patients/${patientId}/documents`);
    });
  }

  return (
    <>
      <Button
        variant="destructive"
        size="sm"
        className={className}
        aria-label={iconOnly ? t("delete") : undefined}
        onClick={() => setOpen(true)}
      >
        <Trash2 className={iconOnly ? "h-5 w-5" : "h-4 w-4"} />
        {!iconOnly && t("delete")}
      </Button>

      <Dialog open={open} onOpenChange={(v) => !isPending && setOpen(v)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteTitle")}</DialogTitle>
            <DialogDescription>{t("deleteWarning")}</DialogDescription>
          </DialogHeader>
          {error && <p className="px-6 text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={isPending}>
              {t("cancel")}
            </Button>
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={isPending}>
              {isPending ? t("deleting") : t("delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
