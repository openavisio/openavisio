"use client";

import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { updateMedication, deleteMedication } from "@/lib/api";
import { StopCircle, Undo2, Trash2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export interface Med {
  id: string;
  status: string;
  // backend-computed: false when stopped OR past the end date. The badge uses it,
  // so the button must too — status alone said "Stoppen" on a row labelled "Beendet"
  // (extraction sets an end date without touching status).
  is_active: boolean;
  medication_display: string;
  dosage_text?: string | null;
  effective_start?: string | null;
  effective_end?: string | null;
}

const today = () => new Date().toISOString().slice(0, 10);

export function MedicationActions({ med, iconBar = false }: { med: Med; iconBar?: boolean }) {
  const t = useTranslations("Med");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Stopping used to silently mean "today" — so a drug she stopped last autumn
  // was recorded as ending the moment you clicked (#128). Ask.
  const [stopOpen, setStopOpen] = useState(false);
  const [stopDate, setStopDate] = useState(today());

  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState({
    medication_display: med.medication_display,
    dosage_text: med.dosage_text ?? "",
    effective_start: med.effective_start ?? "",
    effective_end: med.effective_end ?? "",
  });

  function save(data: Record<string, unknown>, close: () => void) {
    startTransition(async () => {
      await updateMedication(med.id, data);
      close();
      router.refresh();
    });
  }

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    startTransition(async () => {
      await deleteMedication(med.id);
      router.refresh();
    });
  }

  // cursor-pointer: Tailwind v4's reset leaves buttons with the arrow cursor.
  // Each action gets its own hover colour — only delete used to react at all, so
  // the other two felt dead.
  const btn =
    "inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  // "Reaktivieren" is wider than "Stoppen" — without a fixed slot every button
  // behind it shifted depending on the row's state.
  const firstSlot = "w-32 shrink-0";
  const stopBtn = `${btn} hover:border-amber-500 hover:bg-amber-500/10 hover:text-amber-700 dark:hover:text-amber-400`;
  const editBtn = `${btn} hover:border-blue-500 hover:bg-blue-500/10 hover:text-blue-700 dark:hover:text-blue-400`;

  // Phone: the same icon bar documents and conditions reveal on tap.
  const bar = (
    <div className="flex items-stretch divide-x border-t [&>*]:min-h-12 [&>*]:flex-1 [&>*]:justify-center [&>*]:rounded-none [&>*]:border-0"
         onClick={(e) => e.stopPropagation()}>
      {med.is_active ? (
        <button onClick={() => setStopOpen(true)} disabled={pending} aria-label={t("MarkStoppedTitle")}
                className="inline-flex items-center text-foreground disabled:opacity-50">
          <StopCircle className="h-5 w-5" />
        </button>
      ) : (
        <button onClick={() => save({ status: "active", effective_end: null }, () => {})} disabled={pending}
                aria-label={t("MarkActiveTitle")}
                className="inline-flex items-center bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 disabled:opacity-50">
          <Undo2 className="h-5 w-5" />
        </button>
      )}
      <button onClick={() => setEditOpen(true)} disabled={pending} aria-label={t("EditTitle")}
              className="inline-flex items-center text-foreground disabled:opacity-50">
        <Pencil className="h-5 w-5" />
      </button>
      <button onClick={handleDelete} disabled={pending}
              aria-label={confirmDelete ? t("ConfirmAgain") : t("DeleteTitle")}
              className={`inline-flex items-center disabled:opacity-50 ${
                confirmDelete ? "bg-destructive text-destructive-foreground" : "text-destructive"
              }`}>
        <Trash2 className="h-5 w-5" />
        {confirmDelete && <span className="ml-1.5 text-xs font-medium">{t("Confirm")}</span>}
      </button>
    </div>
  );

  const dialogs = (
    <>
      {/* Stop: which day did she actually stop? */}
      <Dialog open={stopOpen} onOpenChange={(v) => !pending && setStopOpen(v)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("StopTitle", { name: med.medication_display })}</DialogTitle>
            <DialogDescription>{t("StopHint")}</DialogDescription>
          </DialogHeader>
          <div className="px-6">
            <label className="text-sm font-medium">{t("EndDate")}</label>
            <input
              type="date"
              value={stopDate}
              max={today()}
              onChange={(e) => setStopDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setStopOpen(false)} disabled={pending}>
              {t("Cancel")}
            </Button>
            <Button
              size="sm"
              disabled={pending || !stopDate}
              onClick={() => save({ status: "stopped", effective_end: stopDate }, () => setStopOpen(false))}
            >
              {pending ? t("Saving") : t("Stop")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit: an extracted dosage or date could not be corrected at all before */}
      <Dialog open={editOpen} onOpenChange={(v) => !pending && setEditOpen(v)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("EditTitle")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6">
            <div>
              <label className="text-sm font-medium">{t("Name")}</label>
              <input
                value={form.medication_display}
                onChange={(e) => setForm({ ...form, medication_display: e.target.value })}
                className="mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium">{t("Dosage")}</label>
              <input
                value={form.dosage_text}
                onChange={(e) => setForm({ ...form, dosage_text: e.target.value })}
                placeholder="1-0-1, 300 mg"
                className="mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-sm font-medium">{t("StartDate")}</label>
                <input
                  type="date"
                  value={form.effective_start}
                  onChange={(e) => setForm({ ...form, effective_start: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
                />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium">{t("EndDate")}</label>
                <input
                  type="date"
                  value={form.effective_end}
                  onChange={(e) => setForm({ ...form, effective_end: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setEditOpen(false)} disabled={pending}>
              {t("Cancel")}
            </Button>
            <Button
              size="sm"
              disabled={pending || !form.medication_display.trim()}
              onClick={() =>
                save(
                  {
                    medication_display: form.medication_display.trim(),
                    // empty string would be stored as an empty date, not as "unknown"
                    dosage_text: form.dosage_text.trim() || null,
                    effective_start: form.effective_start || null,
                    effective_end: form.effective_end || null,
                  },
                  () => setEditOpen(false),
                )
              }
            >
              {pending ? t("Saving") : t("Save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );

  if (iconBar) return (<>{bar}{dialogs}</>);

  return (
    <div className="flex items-center gap-2" onMouseLeave={() => setConfirmDelete(false)}>
      {med.is_active ? (
        <button onClick={() => setStopOpen(true)} disabled={pending} title={t("MarkStoppedTitle")} className={`${stopBtn} ${firstSlot}`}>
          <StopCircle className="h-3.5 w-3.5" />
          {t("Stop")}
        </button>
      ) : (
        <button
          onClick={() => save({ status: "active", effective_end: null }, () => {})}
          disabled={pending}
          title={t("MarkActiveTitle")}
          className={`${btn} ${firstSlot} hover:border-emerald-500 hover:bg-emerald-500/10 hover:text-emerald-700 dark:hover:text-emerald-400`}
        >
          <Undo2 className="h-3.5 w-3.5" />
          {t("Reactivate")}
        </button>
      )}

      <button onClick={() => setEditOpen(true)} disabled={pending} title={t("EditTitle")} className={editBtn}>
        <Pencil className="h-3.5 w-3.5" />
        {t("Edit")}
      </button>

      <button
        onClick={handleDelete}
        disabled={pending}
        title={confirmDelete ? t("ConfirmAgain") : t("DeleteTitle")}
        className={`inline-flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
          confirmDelete
            ? "border-destructive bg-destructive text-destructive-foreground hover:bg-destructive/90"
            : "border-border bg-muted text-foreground hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
        }`}
      >
        <Trash2 className="h-3.5 w-3.5" />
        {confirmDelete ? t("Confirm") : t("Delete")}
      </button>

      {dialogs}

    </div>
  );
}
