import { getTranslations } from "next-intl/server";
import { ShieldCheck, FileText, CalendarClock, AlertTriangle } from "lucide-react";
import { PublicDocumentViewer } from "./PublicDocumentViewer";

const API = process.env.API_URL || "http://localhost:8000";

// External, anonymous page — never index (ADR-021 hardening).
export const metadata = {
  robots: { index: false, follow: false },
};

type PublicDoc = {
  id: string;
  file_name: string | null;
  content_type: string | null;
  size: number | null;
  type: string | null;
  issued_date: string | null;
  extraction: Record<string, any> | null;
};

type PublicShare = {
  patient: { given_name: string; family_name: string; birth_date: string | null };
  org_name: string;
  expires_at: string;
  documents: PublicDoc[];
  handout: { variant: string; lang: string; created_at: string } | null;
};

async function getShare(token: string): Promise<{ data?: PublicShare; status: number }> {
  const res = await fetch(`${API}/api/public/document-shares/${encodeURIComponent(token)}`, {
    cache: "no-store",
    headers: { "X-Robots-Tag": "noindex" },
  });
  if (!res.ok) return { status: res.status };
  return { data: await res.json(), status: 200 };
}

function ExtractionSummary({ json }: { json: Record<string, any> | null }) {
  if (!json) return null;
  const counts = [
    { label: "diagnoses", n: json.diagnoses?.length ?? 0 },
    { label: "medications", n: json.medications?.length ?? 0 },
    { label: "measurements", n: (json.observations ?? []).filter((o: any) => o.category !== "lab").length },
    { label: "lab results", n: (json.observations ?? []).filter((o: any) => o.category === "lab").length },
    { label: "events", n: json.appointments?.length ?? 0 },
    { label: "recommendations", n: json.recommendations?.length ?? 0 },
  ].filter((c) => c.n > 0);
  const summary = typeof json.summary === "string" ? json.summary : null;
  if (!summary && counts.length === 0) return null;
  return (
    <div className="rounded-xl border bg-card p-4 space-y-2">
      {summary && <p className="text-sm">{summary}</p>}
      {counts.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {counts.map((c) => `${c.n} ${c.label}`).join(" · ")}
        </p>
      )}
    </div>
  );
}

export default async function PublicSharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const t = await getTranslations("PublicShare");
  const { data, status } = await getShare(token);

  if (!data) {
    const gone = status === 410;
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
        <div className="max-w-md w-full rounded-xl border bg-card p-8 text-center space-y-3">
          <div className="flex justify-center">
            <div className="rounded-full bg-destructive/10 p-4">
              <AlertTriangle className="size-8 text-destructive" />
            </div>
          </div>
          <h1 className="text-xl font-bold">{gone ? t("goneTitle") : t("notFoundTitle")}</h1>
          <p className="text-sm text-muted-foreground">{gone ? t("goneBody") : t("notFoundBody")}</p>
        </div>
      </div>
    );
  }

  const { patient, org_name, expires_at, documents, handout } = data;

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-card">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="size-5 text-primary" />
            {org_name}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CalendarClock className="size-3.5" />
            {t("validUntil", { date: new Date(expires_at).toLocaleDateString() })}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{t("sharedRecordOf")}</p>
          <h1 className="text-2xl font-bold">{patient.given_name} {patient.family_name}</h1>
          {patient.birth_date && (
            <p className="text-sm text-muted-foreground">{t("born", { date: patient.birth_date })}</p>
          )}
          <div className="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground mt-2">
            <ShieldCheck className="size-4 shrink-0 mt-0.5" />
            <span>{t("readOnlyNotice")}</span>
          </div>
        </div>

        {handout && (
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-muted-foreground" />
              <h2 className="font-semibold">{t(`handout_${handout.variant}`)}</h2>
              <span className="text-xs text-muted-foreground">· {t("handoutAsOf", { date: handout.created_at.slice(0, 10) })}</span>
            </div>
            <PublicDocumentViewer
              token={token}
              src={`/api/public/document-shares/${encodeURIComponent(token)}/handout/file`}
              contentType="application/pdf"
              fileName={t(`handout_${handout.variant}`)}
            />
          </section>
        )}
        {documents.map((doc) => (
          <section key={doc.id} className="space-y-3">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-muted-foreground" />
              <h2 className="font-semibold">{doc.file_name || t("document")}</h2>
              {doc.issued_date && <span className="text-xs text-muted-foreground">· {doc.issued_date}</span>}
            </div>
            <PublicDocumentViewer
              token={token}
              docId={doc.id}
              contentType={doc.content_type ?? "application/pdf"}
              fileName={doc.file_name ?? "document"}
            />
            <ExtractionSummary json={doc.extraction} />
          </section>
        ))}
      </main>
    </div>
  );
}
