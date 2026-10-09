"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Plus, X } from "lucide-react";
import { createGroupAction } from "./actions";

export function CreateGroupButton() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      const result = await createGroupAction(name.trim());
      if (result.error) {
        setError(result.error);
      } else {
        router.push(`/group/${result.id}`);
      }
    });
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90"
      >
        <Plus className="size-3.5" />
        Create Group
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <input
        autoFocus
        type="text"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Group name"
        className="rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background w-48"
      />
      {error && <span className="text-xs text-destructive">{error}</span>}
      <button
        type="submit"
        disabled={pending || !name.trim()}
        className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
      >
        {pending ? "Creating…" : "Create"}
      </button>
      <button
        type="button"
        onClick={() => { setOpen(false); setName(""); setError(""); }}
        className="rounded-lg border px-2 py-1.5 text-sm hover:bg-muted"
      >
        <X className="size-3.5" />
      </button>
    </form>
  );
}
