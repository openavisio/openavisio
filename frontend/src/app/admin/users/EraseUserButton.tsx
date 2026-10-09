"use client";

import { useState, useTransition } from "react";
import { eraseUserAction } from "./actions";

export function EraseUserButton({
  userId,
  userEmail,
}: {
  userId: string;
  userEmail: string;
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  function handleSubmit() {
    setError("");
    startTransition(async () => {
      const result = await eraseUserAction(userId, input);
      if (result?.error) {
        setError(result.error);
      } else {
        setOpen(false);
      }
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
      >
        Erase
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background border rounded-xl shadow-lg p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-destructive mb-2">Erase user account</h2>
            <p className="text-sm text-muted-foreground mb-4">
              This permanently anonymises all personal data for <strong>{userEmail}</strong> and removes
              their login credentials and access grants. This action cannot be undone.
            </p>
            <p className="text-sm mb-2">
              Type <strong>{userEmail}</strong> to confirm:
            </p>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={userEmail}
              className="w-full border rounded px-3 py-2 text-sm mb-3 bg-background"
              autoFocus
            />
            {error && <p className="text-xs text-destructive mb-3">{error}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setOpen(false); setInput(""); setError(""); }}
                disabled={pending}
                className="text-sm px-4 py-2 rounded border hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={pending || input !== userEmail}
                className="text-sm px-4 py-2 rounded bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
              >
                {pending ? "Erasing…" : "Erase permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
