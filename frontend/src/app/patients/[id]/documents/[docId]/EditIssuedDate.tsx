"use client";

import { useState, useTransition } from "react";
import { updateIssuedDateAction } from "./actions";

export function EditIssuedDate({
  docId,
  patientId,
  value,
}: {
  docId: string;
  patientId: string;
  value: string | null;
}) {
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(value ?? "");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit() {
    startTransition(async () => {
      const result = await updateIssuedDateAction(docId, patientId, date || null);
      if (result.error) {
        setError(result.error);
      } else {
        setEditing(false);
        setError(null);
      }
    });
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <span className="font-medium">{value ?? <span className="text-muted-foreground italic">not set</span>}</span>
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-muted-foreground hover:text-foreground underline"
        >
          edit
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        className="text-sm border rounded px-2 py-0.5 bg-background"
        autoFocus
      />
      <button
        onClick={submit}
        disabled={pending}
        className="text-xs font-medium text-primary hover:underline disabled:opacity-50"
      >
        {pending ? "Saving…" : "Save"}
      </button>
      <button
        onClick={() => { setEditing(false); setDate(value ?? ""); setError(null); }}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
