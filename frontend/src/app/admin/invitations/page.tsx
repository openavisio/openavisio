import { AppLayout } from "@/components/layout/AppLayout";
import { getAdminInvitations } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AlertCircle } from "lucide-react";
import { CopyLinkButton } from "./CopyLinkButton";
import { InviteUserButton } from "./InviteUserButton";

export default async function AdminInvitationsPage() {
  let invitations: any[] = [], fetchError = false;
  try { invitations = await getAdminInvitations(); } catch { fetchError = true; }

  return (
    <AppLayout>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-bold">Invitations</h1>
        <InviteUserButton />
      </div>

      {fetchError && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          Failed to load invitations. The server may be unavailable.
        </div>
      )}

      {!fetchError && invitations.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No invitations yet.</div>
      ) : !fetchError ? (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Email</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Expires</th>
                <th className="px-4 py-3 text-left font-medium">Sent</th>
                <th className="px-4 py-3 text-left font-medium">Link</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {invitations.map((inv: any) => {
                const used = inv.is_used;
                const expired = new Date(inv.expires_at) < new Date();
                const statusLabel = used ? "Used" : expired ? "Expired" : "Pending";
                const statusColor = used
                  ? "bg-muted text-muted-foreground"
                  : expired
                  ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                  : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
                return (
                  <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">{inv.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor}`}>
                        {statusLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{formatDate(inv.expires_at)}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{formatDate(inv.created_at)}</td>
                    <td className="px-4 py-3">
                      {!used && !expired && <CopyLinkButton token={inv.token} />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppLayout>
  );
}
