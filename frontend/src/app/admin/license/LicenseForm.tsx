"use client";

import { useState } from "react";
import { deleteLicenseAction, uploadLicenseAction, type LicenseInfo } from "./actions";

function formatDate(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function daysRemaining(iso: string | null): number | null {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

function TierBadge({ info }: { info: LicenseInfo }) {
  if (info.tier === "commercial" && !info.is_grace_period) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
        Commercial
      </span>
    );
  }
  if (info.tier === "commercial" && info.is_grace_period) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
        Commercial (grace period)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
      Personal
    </span>
  );
}

export function LicenseForm({ initialInfo }: { initialInfo: LicenseInfo }) {
  const [info, setInfo] = useState(initialInfo);
  const [token, setToken] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setUploading(true);
    setError("");
    setSuccess("");
    const result = await uploadLicenseAction(token);
    setUploading(false);
    if (result.error) {
      setError(result.error);
    } else {
      setToken("");
      setSuccess("License uploaded successfully.");
      if (result.info) setInfo(result.info);
    }
  }

  async function handleDelete() {
    if (!confirm("Remove the current license? The installation will revert to Personal tier limits.")) return;
    setDeleting(true);
    setError("");
    setSuccess("");
    const result = await deleteLicenseAction();
    setDeleting(false);
    if (result.error) {
      setError(result.error);
    } else {
      setSuccess("License removed.");
      if (result.info) setInfo(result.info);
    }
  }

  const days = daysRemaining(info.expires_at);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-medium text-sm">Current tier</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Determines Patient and User limits for this installation.
            </p>
          </div>
          <TierBadge info={info} />
        </div>

        {info.has_license && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {info.issued_to && (
              <>
                <dt className="text-muted-foreground">Issued to</dt>
                <dd className="font-medium">{info.issued_to}</dd>
              </>
            )}
            {info.expires_at && (
              <>
                <dt className="text-muted-foreground">Expires</dt>
                <dd className="font-medium">{formatDate(info.expires_at)}</dd>
                <dt className="text-muted-foreground">Days remaining</dt>
                <dd className={`font-medium ${days !== null && days <= 30 ? "text-yellow-700 dark:text-yellow-300" : ""}`}>
                  {days !== null && days > 0 ? `${days} days` : "Expired"}
                </dd>
              </>
            )}
            {info.is_grace_period && info.grace_ends_at && (
              <>
                <dt className="text-muted-foreground">Grace period ends</dt>
                <dd className="font-medium text-yellow-700 dark:text-yellow-300">
                  {formatDate(info.grace_ends_at)}
                </dd>
              </>
            )}
            {!info.is_grace_period && info.tier === "personal" && info.expires_at && (
              <>
                <dt className="text-muted-foreground text-destructive">Status</dt>
                <dd className="font-medium text-destructive">Expired — reverted to Personal tier</dd>
              </>
            )}
          </dl>
        )}

        {!info.has_license && (
          <p className="text-xs text-muted-foreground">
            No license installed. Limited to {10} Patients and {3} Users.
          </p>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
        {success && <p className="text-sm text-green-600">{success}</p>}

        {info.has_license && (
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="text-sm text-destructive hover:underline disabled:opacity-50"
          >
            {deleting ? "Removing…" : "Remove license"}
          </button>
        )}
      </div>

      <div className="rounded-xl border bg-card p-6 space-y-4">
        <div>
          <h2 className="font-medium text-sm">Upload license</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Paste the signed license token provided by OpenAvisio.
          </p>
        </div>

        <form onSubmit={handleUpload} className="space-y-3">
          <textarea
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="eyJhbGciOiJSUzI1NiJ9…"
            rows={4}
            required
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono resize-none"
          />

          <button
            type="submit"
            disabled={uploading || !token.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Upload license"}
          </button>
        </form>
      </div>
    </div>
  );
}
