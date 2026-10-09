"use client";

import { useState, useTransition, useRef, useEffect } from "react";
import { setCorrespondentAction, createCorrespondentAction } from "./doc-actions";
import { Check, ChevronDown, Plus, X } from "lucide-react";

type Correspondent = { id: string; name: string };

export function CorrespondentSelect({
  docId,
  patientId,
  current,
  correspondents: initialList,
}: {
  docId: string;
  patientId: string;
  current: Correspondent | null;
  correspondents: Correspondent[];
}) {
  const [list, setList] = useState(initialList);
  const [selected, setSelected] = useState<Correspondent | null>(current);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pending, startTransition] = useTransition();
  const [creating, setCreating] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const filtered = list.filter((c) => c.name.toLowerCase().includes(query.toLowerCase()));
  const exactMatch = list.find((c) => c.name.toLowerCase() === query.toLowerCase().trim());

  function select(c: Correspondent | null) {
    setSelected(c);
    setOpen(false);
    setQuery("");
    startTransition(async () => {
      await setCorrespondentAction(docId, patientId, c?.id ?? null);
    });
  }

  function createNew() {
    const name = query.trim();
    if (!name) return;
    setCreating(true);
    startTransition(async () => {
      const result = await createCorrespondentAction(name);
      if (result.id && result.name) {
        const newC = { id: result.id, name: result.name };
        setList((prev) => [...prev, newC].sort((a, b) => a.name.localeCompare(b.name)));
        select(newC);
      }
      setCreating(false);
    });
  }

  return (
    <div ref={ref} className="relative inline-block text-left min-w-40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={pending}
        className="flex items-center gap-1.5 text-sm font-medium hover:text-primary disabled:opacity-50 transition-colors"
      >
        <span className={selected ? "text-foreground" : "text-muted-foreground"}>
          {selected ? selected.name : "None"}
        </span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute z-20 left-0 mt-1 w-64 rounded-lg border bg-popover shadow-md">
          <div className="p-2 border-b">
            <input
              autoFocus
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search or create…"
              className="w-full rounded-md border px-2.5 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  if (filtered.length === 1) select(filtered[0]);
                  else if (!exactMatch && query.trim()) createNew();
                }
              }}
            />
          </div>

          <ul className="max-h-52 overflow-y-auto py-1">
            {selected && (
              <li>
                <button
                  type="button"
                  onClick={() => select(null)}
                  className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted/50"
                >
                  <X className="size-3.5" />
                  Clear
                </button>
              </li>
            )}
            {filtered.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => select(c)}
                  className="flex items-center gap-2 w-full px-3 py-1.5 text-sm hover:bg-muted/50"
                >
                  {selected?.id === c.id ? (
                    <Check className="size-3.5 text-primary shrink-0" />
                  ) : (
                    <span className="size-3.5 shrink-0" />
                  )}
                  {c.name}
                </button>
              </li>
            ))}
            {query.trim() && !exactMatch && (
              <li>
                <button
                  type="button"
                  onClick={createNew}
                  disabled={creating}
                  className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-primary hover:bg-muted/50 disabled:opacity-50"
                >
                  <Plus className="size-3.5 shrink-0" />
                  {creating ? "Creating…" : `Create "${query.trim()}"`}
                </button>
              </li>
            )}
            {filtered.length === 0 && !query.trim() && (
              <li className="px-3 py-2 text-xs text-muted-foreground">No correspondents yet. Type to create one.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
