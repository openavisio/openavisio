"use client";

import { useState, useEffect, useRef, useCallback, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Upload,
  Camera,
  FileText,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { retryDocument } from "@/lib/api";

const CONCURRENCY = 4;
const ACCEPTED = ".pdf,.jpg,.jpeg,.png";

type Status = "pending" | "uploading" | "done" | "error";

type FileEntry = {
  id: string;
  file: File;
  status: Status;
  progress?: number; // 0–100 while uploading
  error?: string;
};

// XHR instead of fetch: fetch has no upload-progress events (issue #62)
function uploadFile(patientId: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/upload/${patientId}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve();
      let msg = `HTTP ${xhr.status}`;
      try { msg = JSON.parse(xhr.responseText).error || msg; } catch {}
      const err = new Error(msg) as Error & { status?: number };
      err.status = xhr.status;
      reject(err);
    };
    xhr.onerror = () => reject(new Error("network error"));
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

export function UploadPanel({ patientId, demoMode = false }: { patientId: string; demoMode?: boolean }) {
  const router = useRouter();
  const t = useTranslations("DocumentsPage");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const startedRef = useRef(new Set<string>());

  // Demo instances: visitors don't upload their own files — they replay the
  // pipeline with the bundled sample. A previous sample run is deleted first so
  // every visitor gets the full show (the backend refuses everything else by hash).
  async function startSampleUpload() {
    const { getDocuments, deleteDocument } = await import("@/lib/api");
    const existing = await getDocuments(patientId).catch(() => []);
    const dup = (existing as any[]).find((d) => d.file_name === "sample-followup-letter.pdf");
    if (dup) await deleteDocument(dup.id).catch(() => {});
    const blob = await (await fetch("/demo-sample.pdf")).blob();
    addFiles([new File([blob], "sample-followup-letter.pdf", { type: "application/pdf" })]);
  }

  function addFiles(files: FileList | File[]) {
    const newEntries: FileEntry[] = Array.from(files).map((file) => ({
      id: crypto.randomUUID(),
      file,
      status: "pending",
    }));
    setEntries((prev) => [...prev, ...newEntries]);
  }

  // Concurrent upload runner — picks up pending slots whenever entries change
  useEffect(() => {
    const pending = entries.filter(
      (e) => e.status === "pending" && !startedRef.current.has(e.id)
    );
    const uploading = entries.filter((e) => e.status === "uploading");
    const slots = CONCURRENCY - uploading.length;
    if (slots <= 0 || pending.length === 0) return;

    const toStart = pending.slice(0, slots);
    toStart.forEach((e) => startedRef.current.add(e.id));

    setEntries((prev) =>
      prev.map((e) =>
        toStart.some((s) => s.id === e.id) ? { ...e, status: "uploading" } : e
      )
    );

    toStart.forEach((entry) => {
      uploadFile(patientId, entry.file, (pct) =>
        setEntries((prev) =>
          prev.map((e) => (e.id === entry.id ? { ...e, progress: pct } : e))
        )
      )
        .then(() =>
          setEntries((prev) =>
            prev.map((e) => (e.id === entry.id ? { ...e, status: "done", progress: 100 } : e))
          )
        )
        .catch((err) =>
          setEntries((prev) =>
            prev.map((e) =>
              e.id === entry.id
                ? { ...e, status: "error", error: err?.status === 409 ? t("duplicateUpload") : String(err?.message ?? err) }
                : e
            )
          )
        );
    });
  }, [entries, patientId]);

  // Refresh document list once all uploads finish without errors
  useEffect(() => {
    if (entries.length === 0) return;
    const active = entries.filter(
      (e) => e.status === "pending" || e.status === "uploading"
    );
    const failed = entries.filter((e) => e.status === "error");
    if (active.length === 0 && failed.length === 0) {
      router.refresh();
    }
  }, [entries, router]);

  function retryFailed() {
    const failedIds = new Set(
      entries.filter((e) => e.status === "error").map((e) => e.id)
    );
    startedRef.current = new Set(
      [...startedRef.current].filter((id) => !failedIds.has(id))
    );
    setEntries((prev) =>
      prev.map((e) =>
        e.status === "error" ? { ...e, status: "pending", error: undefined } : e
      )
    );
  }

  function dismiss() {
    setEntries([]);
    startedRef.current.clear();
  }

  const done = entries.filter((e) => e.status === "done").length;
  const failed = entries.filter((e) => e.status === "error").length;
  const active = entries.filter(
    (e) => e.status === "pending" || e.status === "uploading"
  ).length;
  const total = entries.length;

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  }, []);

  if (demoMode) {
    return (
      <div className="space-y-3 mb-6">
        <button
          type="button"
          onClick={startSampleUpload}
          className="flex h-28 w-full flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-border px-4 cursor-pointer transition-colors select-none text-center hover:border-primary/50 hover:bg-muted/30"
        >
          <Upload className="h-7 w-7 text-muted-foreground shrink-0" />
          <span className="text-sm font-medium">{t("demoUploadButton")}</span>
          <span className="text-xs text-muted-foreground">{t("demoUploadHint")}</span>
        </button>
        {entries.length > 0 && (
          <div className="space-y-1">
            {entries.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2">
                <StatusIcon status={entry.status} />
                <span className="truncate flex-1 text-xs text-muted-foreground">{entry.file.name}</span>
                {entry.status === "error" && (
                  <span className="text-xs text-destructive">{entry.error}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 mb-6">
      <div className="flex gap-2">
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex h-28 flex-1 flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed px-4 cursor-pointer transition-colors select-none text-center ${
            dragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/30"
          }`}
        >
          <Upload className="h-7 w-7 text-muted-foreground shrink-0" />
          <span className="text-sm font-medium">{t("dropHint")}</span>
          <span className="text-xs text-muted-foreground">PDF, JPG, PNG</span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </div>
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          className="flex size-28 flex-col items-center justify-center gap-1.5 rounded-xl border px-2 text-sm font-medium hover:bg-muted/50 transition-colors shrink-0"
        >
          <Camera className="h-6 w-6" />
          <span className="hidden sm:inline">{t("takePhoto")}</span>
        </button>
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {total > 0 && (
        <div className="rounded-xl border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {active > 0
                ? t("uploading", { done, total })
                : failed > 0
                ? t("uploadResult", { done, failed })
                : t("uploadedBackground", { total })}
            </span>
            <div className="flex items-center gap-3">
              {failed > 0 && active === 0 && (
                <button
                  onClick={retryFailed}
                  className="flex items-center gap-1 text-xs font-medium text-orange-600 hover:text-orange-500"
                >
                  <RefreshCw className="h-3 w-3" />
                  {t("retryFailed")}
                </button>
              )}
              {active === 0 && (
                <button
                  onClick={dismiss}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  {t("dismiss")}
                </button>
              )}
            </div>
          </div>

          <div className="space-y-1 max-h-40 overflow-y-auto">
            {entries.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2">
                <StatusIcon status={entry.status} />
                <span className="truncate flex-1 text-xs text-muted-foreground">
                  {entry.file.name}
                </span>
                {entry.status === "uploading" && (
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="h-1 w-20 rounded-full bg-muted overflow-hidden">
                      <span
                        className="block h-full bg-primary transition-all"
                        style={{ width: `${entry.progress ?? 0}%` }}
                      />
                    </span>
                    <span className="text-xs tabular-nums text-muted-foreground w-8 text-right">
                      {entry.progress ?? 0}%
                    </span>
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />;
    case "error":
      return <XCircle className="h-3.5 w-3.5 text-destructive shrink-0" />;
    case "uploading":
      return (
        <Loader2 className="h-3.5 w-3.5 text-primary animate-spin shrink-0" />
      );
    default:
      return <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />;
  }
}

export function RetryButton({ docId }: { docId: string }) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function retry() {
    startTransition(async () => {
      await retryDocument(docId);
      router.refresh();
    });
  }

  return (
    <button
      onClick={retry}
      disabled={pending}
      className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950/20 disabled:opacity-50 transition-colors"
    >
      <RefreshCw className={`h-4 w-4 ${pending ? "animate-spin" : ""}`} />
      {pending ? "Retrying…" : "Retry"}
    </button>
  );
}

export function RetryAllButton({ failedDocIds }: { failedDocIds: string[] }) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function retryAll() {
    startTransition(async () => {
      await Promise.all(failedDocIds.map((id) => retryDocument(id)));
      router.refresh();
    });
  }

  return (
    <button
      onClick={retryAll}
      disabled={pending}
      className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950/20 disabled:opacity-50 transition-colors"
    >
      <RefreshCw className="h-3.5 w-3.5" />
      {pending ? "Retrying…" : `Retry ${failedDocIds.length} failed`}
    </button>
  );
}
