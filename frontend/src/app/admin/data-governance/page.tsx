import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { DataGovernanceClient } from "./DataGovernanceClient";

const API = process.env.API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

export default async function DataGovernancePage() {
  const session = await auth();
  const token = (session as any)?.accessToken;

  let categories: any[] = [];
  try {
    const res = await fetch(`${API}/api/admin/data-categories`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) categories = await res.json();
  } catch {}

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-1">Data governance</h1>
      <p className="text-sm text-muted-foreground mb-4">
        GDPR lawful basis and retention policy per data category (Art. 5(1)(e), Art. 6/9).
      </p>
      <div className="max-w-3xl">
        <DataGovernanceClient categories={categories} />
      </div>
    </AppLayout>
  );
}
