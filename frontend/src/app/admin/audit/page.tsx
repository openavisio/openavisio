import { AppLayout } from "@/components/layout/AppLayout";
import { getAuditLog } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default async function AdminAuditPage() {
  const result = await getAuditLog().catch(() => ({ items: [], total: 0 }));
  const entries = result?.items ?? [];

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-6">Audit Log</h1>

      {entries.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No audit entries.</div>
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">When</th>
                <th className="px-4 py-3 text-left font-medium">User</th>
                <th className="px-4 py-3 text-left font-medium">Action</th>
                <th className="px-4 py-3 text-left font-medium">Entity</th>
                <th className="px-4 py-3 text-left font-medium">Entity ID</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {entries.map((e: any) => (
                <tr key={e.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(e.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-xs">{e.user_name ?? "system"}</td>
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
              Showing {entries.length} of {result.total} entries.
            </div>
          )}
        </div>
      )}
    </AppLayout>
  );
}
