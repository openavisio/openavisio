"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle } from "lucide-react";

export function CreatedBanner() {
  const params = useSearchParams();
  const router = useRouter();
  const created = params.get("created") === "1";

  useEffect(() => {
    if (created) {
      // Remove the query param from the URL without re-rendering
      const url = new URL(window.location.href);
      url.searchParams.delete("created");
      window.history.replaceState({}, "", url.toString());
    }
  }, [created]);

  if (!created) return null;

  return (
    <div className="flex items-center gap-2 rounded-lg bg-green-500/10 text-green-700 dark:text-green-400 px-4 py-3 text-sm">
      <CheckCircle className="size-4 shrink-0" />
      Patient created successfully.
    </div>
  );
}
