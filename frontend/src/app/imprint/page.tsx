import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getOrganization } from "@/lib/api";
import { OperatorDetails, hasOperatorDetails, type Operator } from "@/components/OperatorDetails";

export const dynamic = "force-dynamic";

// §5 DDG makes this mandatory for a German operator, and the app had none.
// The details belong to whoever RUNS the instance — a household, a Verein, a
// care organisation — so they come from the database, not from this repository.
export default async function ImprintPage() {
  let org: Operator & { name?: string } = {};
  try {
    org = await getOrganization();
  } catch {}

  const complete = hasOperatorDetails(org);

  return (
    <div className="min-h-screen bg-muted/40 py-12 px-4">
      <div className="mx-auto max-w-3xl space-y-8 rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-2">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            <ArrowLeft className="size-4" />
            Zurück zur App
          </Link>
        </div>

        <div>
          <h1 className="mb-1 text-2xl font-bold">Impressum</h1>
          <p className="text-sm text-muted-foreground">Angaben gemäß § 5 DDG</p>
        </div>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Betreiber dieser Installation</h2>
          <OperatorDetails
            operator={org}
            missingLabel="Für diese Installation sind noch keine Betreiberangaben hinterlegt. Ein Impressum ist in Deutschland nach § 5 DDG verpflichtend, sobald der Dienst über den rein privaten Gebrauch hinaus angeboten wird."
            missingCta="Jetzt in den Organisationseinstellungen hinterlegen"
          />
        </section>

        {complete && (
          <>
            {org.legal_responsible && (
              <section className="space-y-2">
                <h2 className="text-lg font-semibold">Verantwortlich für den Inhalt</h2>
                <p className="text-sm text-muted-foreground">{org.legal_responsible}</p>
              </section>
            )}

            {(org.legal_register || org.legal_vat_id) && (
              <section className="space-y-2">
                <h2 className="text-lg font-semibold">Registereintrag und Steuer</h2>
                {org.legal_register && (
                  <p className="text-sm text-muted-foreground">{org.legal_register}</p>
                )}
                {org.legal_vat_id && (
                  <p className="text-sm text-muted-foreground">
                    Umsatzsteuer-Identifikationsnummer: {org.legal_vat_id}
                  </p>
                )}
              </section>
            )}
          </>
        )}

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Software</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Diese Instanz läuft mit OpenAvisio, einer quelloffenen Software (AGPL-3.0). Der
            Betreiber dieser Installation ist für die verarbeiteten Daten verantwortlich, nicht
            die Entwickler der Software.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Datenschutz</h2>
          <p className="text-sm text-muted-foreground">
            Informationen zur Verarbeitung Ihrer Daten finden Sie in der{" "}
            <Link href="/privacy" className="underline">Datenschutzerklärung</Link>.
          </p>
        </section>
      </div>
    </div>
  );
}
