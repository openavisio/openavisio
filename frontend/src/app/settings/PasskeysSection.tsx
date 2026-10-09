"use client";

import { useState } from "react";
import { registerPasskeyAction, renamePasskeyAction, deletePasskeyAction } from "./actions";
import { formatDate } from "@/lib/utils";

interface Passkey {
  id: string;
  label: string;
  aaguid: string | null;
  created_at: string;
  last_used_at: string | null;
}

interface Props {
  initialPasskeys: Passkey[];
}

export function PasskeysSection({ initialPasskeys }: Props) {
  const [passkeys, setPasskeys] = useState<Passkey[]>(initialPasskeys);
  const [adding, setAdding] = useState(false);
  const [addLabel, setAddLabel] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [error, setError] = useState("");

  async function handleAdd() {
    if (!window.PublicKeyCredential) {
      setError("Your browser doesn't support passkeys.");
      return;
    }
    setAdding(true);
    setError("");
    try {
      const beginRes = await fetch("/api/auth/passkey/register/begin");
      if (!beginRes.ok) throw new Error("begin failed");
      const options = await beginRes.json();

      const { startRegistration } = await import("@simplewebauthn/browser");
      const credential = await startRegistration({ optionsJSON: options });

      const result = await registerPasskeyAction(
        credential,
        addLabel.trim() || "Passkey"
      );
      if (result.error) {
        setError(result.error);
      } else if (result.passkey) {
        setPasskeys((prev) => [...prev, result.passkey]);
        setAddLabel("");
      }
    } catch (e: any) {
      if (e?.name !== "NotAllowedError") {
        setError("Failed to add passkey. Please try again.");
      }
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: string) {
    const result = await deletePasskeyAction(id);
    if (!result.error) {
      setPasskeys((prev) => prev.filter((p) => p.id !== id));
    } else {
      setError(result.error);
    }
  }

  async function handleRename(id: string) {
    const label = editLabel.trim();
    if (!label) return;
    const result = await renamePasskeyAction(id, label);
    if (!result.error) {
      setPasskeys((prev) => prev.map((p) => (p.id === id ? { ...p, label } : p)));
      setEditingId(null);
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {passkeys.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border">
          {passkeys.map((p) => (
            <li key={p.id} className="flex items-center gap-3 px-4 py-3">
              <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 11V7a5 5 0 0 1 10 0v4M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z" />
              </svg>
              <div className="flex-1 min-w-0">
                {editingId === p.id ? (
                  <form
                    onSubmit={(e) => { e.preventDefault(); handleRename(p.id); }}
                    className="flex items-center gap-2"
                  >
                    <input
                      autoFocus
                      value={editLabel}
                      onChange={(e) => setEditLabel(e.target.value)}
                      onKeyDown={(e) => e.key === "Escape" && setEditingId(null)}
                      className="rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background w-40"
                    />
                    <button type="submit" className="text-xs text-primary hover:underline">Save</button>
                    <button type="button" onClick={() => setEditingId(null)} className="text-xs text-muted-foreground hover:underline">Cancel</button>
                  </form>
                ) : (
                  <>
                    <p className="text-sm font-medium truncate">{p.label}</p>
                    <p className="text-xs text-muted-foreground">
                      Added {formatDate(p.created_at)}
                      {p.last_used_at && ` · Last used ${formatDate(p.last_used_at)}`}
                    </p>
                  </>
                )}
              </div>
              {editingId !== p.id && (
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => { setEditingId(p.id); setEditLabel(p.label); }}
                    className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    title="Rename"
                  >
                    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(p.id)}
                    className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-muted transition-colors"
                    title="Delete"
                  >
                    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4h6v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Passkey name (e.g. MacBook Touch ID)"
          value={addLabel}
          onChange={(e) => setAddLabel(e.target.value)}
          className="rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background flex-1"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={adding}
          className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 shrink-0"
        >
          {adding ? "..." : "Add passkey"}
        </button>
      </div>
    </div>
  );
}
