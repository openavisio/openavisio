import { AppLayout } from "@/components/layout/AppLayout";
import { getAuditLog } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { getTranslations } from "next-intl/server";

export default async function AdminAuditPage() {
  const result = await getAuditLog().catch(() => ({ items: [], total: 0 }));
  const entries = result?.items ?? [];
  const t = await getTranslations("Audit");

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-6">{t("Title")}</h1>

      {entries.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("When")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("User")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Action")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Entity")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("EntityId")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {entries.map((e: any) => (
                <tr key={e.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(e.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-xs">{e.user_name ?? t("System")}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      e.action === "created" ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" :
                      e.action === "deleted" ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300" :
                      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                    }`}>
                      {e.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{e.entity_type}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground font-mono truncate max-w-[120px]">
                    {e.entity_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.total > entries.length && (
            <div className="px-4 py-3 text-xs text-muted-foreground border-t">
              {t("Showing", { shown: entries.length, total: result.total })}
            </div>
          )}
        </div>
      )}
    </AppLayout>
  );
}
