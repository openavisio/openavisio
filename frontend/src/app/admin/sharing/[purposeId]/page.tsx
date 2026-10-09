import { AppLayout } from "@/components/layout/AppLayout";
import { getSharingPurpose, getCollectedShares } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AlertCircle, Download, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ClosePurposeButton } from "../ClosePurposeButton";

function formatSize(bytes: number | null): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default async function SharingPurposeDetailPage({ params }: { params: Promise<{ purposeId: string }> }) {
  const { purposeId } = await params;

  let purpose: any = null;
  let shares: any[] = [];
  let fetchError = false;
  try {
    [purpose, shares] = await Promise.all([
      getSharingPurpose(purposeId),
      getCollectedShares(purposeId),
    ]);
  } catch {
    fetchError = true;
  }
  if (!fetchError && !purpose) notFound();

  return (
    <AppLayout>
      <Link href="/admin/sharing" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="size-4" /> Back to data sharing
      </Link>

      {fetchError && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          Failed to load this sharing purpose.
        </div>
      )}

      {!fetchError && purpose && (
        <>
          <div className="flex items-start justify-between gap-4 flex-wrap mb-1">
            <div>
              <h1 className="text-xl font-bold">{purpose.name}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                {purpose.description ? `Requested: ${purpose.description}` : "No data description"}
                {" · "}
                <span className="capitalize">{purpose.identification_mode}</span>
                {" · "}
                <span className="capitalize">{purpose.status}</span>
                {purpose.expires_at && ` · expires ${formatDate(purpose.expires_at)}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {shares.length > 0 && (
                <a
                  href={`/api/sharing-purposes/${purposeId}/download`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90"
                >
                  <Download className="size-3.5" /> Download all (ZIP)
                </a>
              )}
              {purpose.status === "open" && <ClosePurposeButton purposeId={purposeId} />}
            </div>
          </div>

          {purpose.identification_mode === "anonymous" && (
            <p className="text-xs text-muted-foreground mb-4">
              Anonymous purpose — patients are shown as pseudonyms. File contents are unchanged and may still contain identifying information.
            </p>
          )}

          <div className="mt-4 rounded-xl border bg-card overflow-hidden">
            {shares.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">No files shared yet.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Patient</th>
                    <th className="px-4 py-3 text-left font-medium">File</th>
                    <th className="px-4 py-3 text-left font-medium">Size</th>
                    <th className="px-4 py-3 text-left font-medium">Shared</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {shares.map((s) => (
                    <tr key={s.share_id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">{s.patient_label}</td>
                      <td className="px-4 py-3 text-muted-foreground">{s.file_name || "—"}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatSize(s.size)}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(s.consented_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <a
                          href={`/api/shares/${s.share_id}/file`}
                          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted"
                        >
                          <Download className="size-3.5" /> Download
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </AppLayout>
  );
}
