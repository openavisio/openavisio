import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getTranslations } from "next-intl/server";
import { DataGovernanceClient } from "./DataGovernanceClient";
import type { S } from "@/lib/api";
import { backendFetch } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function DataGovernancePage() {
  const t = await getTranslations("AdminGovernance");
  const session = await auth();
  const token = session?.accessToken;

  let categories: S<"DataCategoryDto">[] = [];
  try {
    const res = await backendFetch(`/api/admin/data-categories`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) categories = await res.json();
  } catch {}

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-1">{t("Title")}</h1>
      <p className="text-sm text-muted-foreground mb-4">
        {t("Intro")}
      </p>
      <div className="max-w-3xl">
        <DataGovernanceClient categories={categories} />
      </div>
    </AppLayout>
  );
}
