import { AppLayout } from "@/components/layout/AppLayout";
import { getSharingPurposes } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AlertCircle, FolderOpen } from "lucide-react";
import Link from "next/link";
import { CreatePurposeForm } from "./CreatePurposeForm";

export default async function AdminSharingPage() {
  let purposes: any[] = [];
  let fetchError = false;
  try {
    purposes = await getSharingPurposes();
  } catch {
    fetchError = true;
  }

  return (
    <AppLayout>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div>
          <h1 className="text-xl font-bold">Data sharing</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Request files (e.g. EEG data) from patients for a study. Caregivers choose which files to share and consent on the patient page.
          </p>
        </div>
      </div>

      <div className="mb-6">
        <CreatePurposeForm />
      </div>

      {fetchError && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          Failed to load sharing purposes. You may not have permission, or the server is unavailable.
        </div>
      )}

      {!fetchError && purposes.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No sharing purposes yet.</div>
      ) : !fetchError ? (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Requested</th>
                <th className="px-4 py-3 text-left font-medium">Identification</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Files</th>
                <th className="px-4 py-3 text-left font-medium">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {purposes.map((p) => (
                <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{p.description || "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground capitalize">{p.identification_mode}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${p.status === "open" ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300" : "bg-muted text-muted-foreground"}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{p.share_count}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(p.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/admin/sharing/${p.id}`} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted">
                      <FolderOpen className="size-3.5" /> View files
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppLayout>
  );
}
