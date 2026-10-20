import { AppLayout } from "@/components/layout/AppLayout";
import { getSystemInfo } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { AlertCircle, Server, Database, Zap, HardDrive, Users } from "lucide-react";

export const dynamic = "force-dynamic";

function Card({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <h2 className="font-semibold text-sm">{title}</h2>
      </div>
      <dl className="space-y-2 text-sm">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd className="font-medium text-right break-all">{value}</dd>
    </div>
  );
}

function DiskBar({ pct }: { pct: number }) {
  const color = pct > 90 ? "bg-destructive" : pct > 75 ? "bg-yellow-500" : "bg-primary";
  return (
    <div className="w-full bg-muted rounded-full h-1.5 mt-1">
      <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export default async function AdminSystemPage() {
  const t = await getTranslations("AdminSystem");
  let info: any = null;
  let error = false;

  try {
    info = await getSystemInfo();
  } catch {
    error = true;
  }

  return (
    <AppLayout>
      <h1 className="text-xl font-bold">{t("Title")}</h1>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadFailed")}
        </div>
      )}

      {info && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {/* Runtime */}
          <Card title={t("Runtime")} icon={Server}>
            <Row label={t("Version")} value={info.runtime?.app_version} />
            <Row
              label="Commit"
              value={
                info.runtime?.commit && info.runtime.commit !== "unknown" ? (
                  <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">{info.runtime.commit}</code>
                ) : null
              }
            />
            <Row label="Python" value={info.runtime?.python_version} />
            <Row label="FastAPI" value={info.runtime?.fastapi_version} />
            <Row label="Pydantic" value={info.runtime?.pydantic_version} />
            <Row label={t("Platform")} value={info.runtime?.platform} />
            <Row label="PID" value={info.runtime?.pid} />
            <Row label={t("Uptime")} value={info.runtime?.process_uptime} />
          </Card>

          {/* Counts */}
          <Card title={t("Data")} icon={Users}>
            <Row label={t("Users")} value={info.counts?.users} />
            <Row label={t("Patients")} value={info.counts?.patients} />
            <Row label={t("Documents")} value={info.counts?.documents} />
          </Card>

          {/* Database */}
          <Card title="PostgreSQL" icon={Database}>
            <Row label={t("Size")} value={info.database?.size} />
            <Row label={t("Tables")} value={info.database?.tables} />
            <Row
              label={t("Version")}
              value={
                <span className="text-xs text-muted-foreground font-normal">
                  {info.database?.version?.split(" ").slice(0, 2).join(" ")}
                </span>
              }
            />
          </Card>

          {/* Redis */}
          {info.redis && Object.keys(info.redis).length > 0 && (
            <Card title="Redis" icon={Zap}>
              <Row label={t("Version")} value={info.redis?.version} />
              <Row label={t("MemoryUsed")} value={info.redis?.used_memory_human} />
              <Row label={t("Clients")} value={info.redis?.connected_clients} />
              <Row
                label={t("Uptime")}
                value={(() => {
                  const s = info.redis?.uptime_in_seconds ?? 0;
                  const h = Math.floor(s / 3600);
                  const m = Math.floor((s % 3600) / 60);
                  return `${h}h ${m}m`;
                })()}
              />
            </Card>
          )}

          {/* Storage */}
          {info.storage && Object.keys(info.storage).length > 0 && (
            <Card title={t("DocumentStorage")} icon={HardDrive}>
              <Row label={t("Total")} value={info.storage?.total} />
              <Row label={t("Used")} value={info.storage?.used} />
              <Row label={t("Free")} value={info.storage?.free} />
              <div>
                <div className="flex justify-between text-xs text-muted-foreground mb-0.5">
                  <span>{t("Usage")}</span>
                  <span>{info.storage?.pct}%</span>
                </div>
                <DiskBar pct={info.storage?.pct ?? 0} />
              </div>
            </Card>
          )}
        </div>
      )}
    </AppLayout>
  );
}
