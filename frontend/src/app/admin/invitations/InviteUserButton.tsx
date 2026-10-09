"use client";

import { useState, useTransition } from "react";
import { UserPlus, Copy, Check, X } from "lucide-react";
import { createInvitation } from "@/lib/api";
import { useRouter } from "next/navigation";

export function InviteUserButton() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInviteUrl("");
    startTransition(async () => {
      try {
        const inv = await createInvitation(email.trim());
        setInviteUrl(`${window.location.origin}/register?token=${inv.token}`);
        setEmail("");
        router.refresh();
      } catch (err: any) {
        setError(err?.message ?? "Failed to create invitation.");
      }
    });
  }

  function copy() {
    navigator.clipboard.writeText(inviteUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function close() {
    setOpen(false);
    setEmail("");
    setInviteUrl("");
    setError("");
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90"
      >
        <UserPlus className="size-4" />
        Invite user
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 w-full sm:w-auto sm:min-w-80">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Invite a new user</p>
        <button onClick={close} className="text-muted-foreground hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>

      {!inviteUrl ? (
        <form onSubmit={submit} className="flex gap-2">
          <input
            autoFocus
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@example.com"
            className="flex-1 rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
          <button
            type="submit"
            disabled={pending}
            className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {pending ? "Sending…" : "Send"}
          </button>
        </form>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Invitation created. Share this link:</p>
          <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
            <code className="flex-1 truncate text-xs">{inviteUrl}</code>
            <button onClick={copy} className="shrink-0 text-muted-foreground hover:text-foreground">
              {copied ? <Check className="size-3.5 text-green-600" /> : <Copy className="size-3.5" />}
            </button>
          </div>
          <button
            onClick={() => { setInviteUrl(""); setEmail(""); }}
            className="text-xs text-primary hover:underline"
          >
            Invite another
          </button>
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
