import { AppLayout } from "@/components/layout/AppLayout";

// Card outlines while the list loads, so a slow connection shows the page shape at once.
export default function Loading() {
  return (
    <AppLayout>
      <div className="mb-6 h-5 w-48 animate-pulse rounded bg-muted" />
      <div className="mb-6 h-24 animate-pulse rounded-xl border bg-muted/40" />
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="flex gap-3 rounded-xl border bg-card p-4">
            <div className="size-9 shrink-0 animate-pulse rounded-lg bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
              <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/4 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </div>
    </AppLayout>
  );
}
