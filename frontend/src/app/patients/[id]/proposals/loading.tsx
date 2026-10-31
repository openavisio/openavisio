import { AppLayout } from "@/components/layout/AppLayout";
import { getTranslations } from "next-intl/server";
import { Loader2 } from "lucide-react";

// The first open groups all diagnoses with the model, which takes a while (ADR 058).
export default async function Loading() {
  const t = await getTranslations("ProposalReview");
  return (
    <AppLayout>
      <div className="space-y-4" aria-busy="true">
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p className="max-w-md text-base font-medium">{t("Grouping")}</p>
        </div>
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="space-y-3 rounded-xl border bg-card p-4">
            <div className="h-8 w-1/2 animate-pulse rounded bg-muted" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </AppLayout>
  );
}
