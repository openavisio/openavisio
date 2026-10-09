"use client";

import { useState } from "react";
import { Info } from "lucide-react";

export function ConditionName({ name }: { name: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = name.length > 40;

  if (!isLong) return <span>{name}</span>;

  return (
    <div>
      <div className="flex items-center gap-1.5">
        <span
          className="truncate block max-w-[12rem] lg:max-w-[22rem]"
          title={name}
        >
          {name}
        </span>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="lg:hidden shrink-0 text-muted-foreground hover:text-foreground"
          aria-label="Show full name"
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </div>
      {expanded && (
        <div className="lg:hidden mt-1.5 text-xs text-muted-foreground bg-muted rounded-md px-2 py-1.5 leading-snug">
          {name}
        </div>
      )}
    </div>
  );
}
