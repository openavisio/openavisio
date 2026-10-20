import { AppLayout } from "@/components/layout/AppLayout";
import { getOllamaStatus } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { AiModelConfig } from "./AiModelConfig";

export default async function AdminOllamaPage() {
  const status = await getOllamaStatus().catch(() => null);
  const t = await getTranslations("AdminAi");

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-6">{t("Title")}</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-6">
        <div className="rounded-xl border bg-card p-5">
          <div className="text-xs text-muted-foreground mb-1">Backend</div>
          <div className="text-sm font-mono truncate">{status?.backend ?? "—"}</div>
        </div>
        <div className="rounded-xl border bg-card p-5">
          <div className="text-xs text-muted-foreground mb-1">{t("Status")}</div>
          <div className={`text-lg font-semibold ${status?.connected ? "text-green-600" : "text-red-500"}`}>
            {status?.connected ? t("Connected") : t("Disconnected")}
          </div>
        </div>
        <div className="rounded-xl border bg-card p-5">
          <div className="text-xs text-muted-foreground mb-1">URL</div>
          <div className="text-sm font-mono truncate">{status?.url ?? "—"}</div>
        </div>
      </div>

      {status?.models && status.models.length > 0 && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">{t("AvailableModels")}</div>
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-xs">{t("Model")}</th>
                <th className="px-4 py-2 text-left font-medium text-xs">{t("Size")}</th>
                <th className="px-4 py-2 text-left font-medium text-xs">{t("Modified")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {status.models.map((m: any) => (
                <tr key={m.name} className="hover:bg-muted/30">
                  <td className="px-4 py-2 font-mono text-xs">{m.name}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {m.size ? `${(m.size / 1e9).toFixed(1)} GB` : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">{m.modified_at?.split("T")[0] ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AiModelConfig
        models={status?.models ?? []}
        initial={{
          extract_model: status?.extract_model,
          classify_model: status?.classify_model,
          chat_model: status?.chat_model,
          vision_model: status?.vision_model,
        }}
      />
    </AppLayout>
  );
}
