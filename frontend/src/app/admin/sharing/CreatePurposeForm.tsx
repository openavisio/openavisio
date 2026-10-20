"use client";

import { useState, useTransition } from "react";
import { Plus, ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { createPurposeAction } from "./sharing-admin-actions";

export function CreatePurposeForm() {
  const t = useTranslations("AdminSharing");
  const tc = useTranslations("Common");
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
        <span className="flex items-center gap-2"><Plus className="size-4 text-muted-foreground" /> {t("NewPurpose")}</span>
        <ChevronDown className={`size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <form onSubmit={submit} className="border-t p-4 space-y-3">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1 sm:col-span-2">
              <label className="text-xs font-medium">{tc("Name")}</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} placeholder={t("NamePlaceholder")}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <label className="text-xs font-medium">{t("WhatData")}</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("WhatDataPlaceholder")}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{t("Identification")}</label>
              <select value={mode} onChange={(e) => setMode(e.target.value)}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary">
                <option value="identified">{t("ModeIdentifiedOption")}</option>
                <option value="anonymous">{t("ModeAnonymousOption")}</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{t("ExpiresOptional")}</label>
              <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)}
                className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>
          <button type="submit" disabled={pending}
            className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            <Plus className="size-3.5" /> {pending ? t("Creating") : tc("Create")}
          </button>
        </form>
      )}
    </div>
  );
}
