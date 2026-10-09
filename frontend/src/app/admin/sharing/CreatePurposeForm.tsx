"use client";

import { useState, useTransition } from "react";
import { Plus, ChevronDown } from "lucide-react";
import { createPurposeAction } from "./sharing-admin-actions";

export function CreatePurposeForm() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState("identified");
  const [expires, setExpires] = useState("");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      const r = await createPurposeAction({
        name,
        description,
        identification_mode: mode,
        expires_at: expires ? new Date(expires).toISOString() : null,
      });
      if (r.error) setError(r.error);
      else {
        setName(""); setDescription(""); setMode("identified"); setExpires("");
        setOpen(false);
      }
    });
  }

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50 transition-colors"
      >
        <span className="flex items-center gap-2"><Plus className="size-4 text-muted-foreground" /> New sharing purpose</span>
        <ChevronDown className={`size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <form onSubmit={submit} className="border-t p-4 space-y-3">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1 sm:col-span-2">
              <label className="text-xs font-medium">Name</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Epilepsy Study 2026"
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <label className="text-xs font-medium">What data is requested?</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. EEG recordings"
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Identification</label>
              <select value={mode} onChange={(e) => setMode(e.target.value)}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary">
                <option value="identified">Identified — show patient name</option>
                <option value="anonymous">Anonymous — pseudonym only</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Expires (optional)</label>
              <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>
          <button type="submit" disabled={pending}
            className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            <Plus className="size-3.5" /> {pending ? "Creating…" : "Create"}
          </button>
        </form>
      )}
    </div>
  );
}
