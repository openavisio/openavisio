import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getOrganization } from "@/lib/api";
import { OperatorDetails, type Operator } from "@/components/OperatorDetails";

export const dynamic = "force-dynamic";

export default async function PrivacyPage() {
  // The controller is the OPERATOR of this instance, so the details come from the
  // database. They used to be `[ORGANISATIONS-NAME]` placeholders shipped to
  // production — a notice that looks legal and is not (#112).
  let org: Operator = {};
  try {
    org = await getOrganization();
  } catch {}

  return (
    <div className="min-h-screen bg-muted/40 py-12 px-4">
      <div className="max-w-3xl mx-auto bg-card rounded-xl shadow-sm border p-8 space-y-8">
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
          <h1 className="text-2xl font-bold mb-1">Datenschutzerklärung</h1>
          <p className="text-sm text-muted-foreground">
            Gemäß Art. 13 und 14 DSGVO ·{" "}
            <Link href="/imprint" className="underline hover:text-foreground">Impressum</Link>
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">1. Verantwortlicher</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Verantwortlicher im Sinne der DSGVO für diese OpenAvisio-Installation ist:
          </p>
          <OperatorDetails
            operator={org}
            missingLabel="Für diese Installation sind noch keine Betreiberangaben hinterlegt. Ohne sie ist diese Datenschutzerklärung unvollständig — Art. 13 DSGVO verlangt die Nennung des Verantwortlichen."
            missingCta="Jetzt in den Organisationseinstellungen hinterlegen"
          />
          {org.dpo_contact && (
            <p className="text-sm text-muted-foreground">
              <span className="font-medium">Datenschutzbeauftragte:r:</span> {org.dpo_contact}
            </p>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">2. Zwecke und Rechtsgrundlagen der Verarbeitung</h2>
          <p className="text-sm leading-relaxed">
            OpenAvisio verarbeitet personenbezogene Daten und besondere Kategorien personenbezogener Daten (Gesundheitsdaten gemäß Art. 9 DSGVO) zu folgenden Zwecken:
          </p>
          <ul className="text-sm space-y-2 list-disc list-inside text-muted-foreground">
            <li><strong>Verwaltung von Patientenakten</strong> — Speicherung und Verarbeitung medizinischer Dokumente und klinischer Daten. Rechtsgrundlage: Art. 9 Abs. 2 lit. h DSGVO (Gesundheitsversorgung) oder Art. 9 Abs. 2 lit. a DSGVO (ausdrückliche Einwilligung).</li>
            <li><strong>Benutzerkontenverwaltung</strong> — Authentifizierung und Zugriffsverwaltung. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung).</li>
            <li><strong>KI-gestützte Dokumentenverarbeitung</strong> — Automatische Extraktion strukturierter Daten aus hochgeladenen Dokumenten. Rechtsgrundlage: Art. 9 Abs. 2 lit. h bzw. a DSGVO.</li>
            <li><strong>Protokollierung (Audit-Log)</strong> — Nachvollziehbarkeit von Datenänderungen. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO (rechtliche Verpflichtung nach Art. 5 Abs. 2 DSGVO).</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">3. Kategorien verarbeiteter Daten</h2>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>Stammdaten von Benutzern: Name, E-Mail-Adresse, Rolle</li>
            <li>Authentifizierungsdaten: gehashte Passwörter, Passkey-Anmeldeinformationen</li>
            <li>Patientendaten: Name, Geburtsdatum, Geschlecht</li>
            <li>Gesundheitsdaten (Art. 9 DSGVO): Diagnosen, Medikamente, Messwerte, Laborergebnisse, Vorfälle, Ereignisse, Gesundheitstagebuch, Empfehlungen</li>
            <li>Medizinische Dokumente: hochgeladene PDFs und Bilder</li>
            <li>Protokolldaten: Aktionen im System mit Zeitstempel und Benutzerangabe</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">4. Empfänger der Daten</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Patientendaten werden ausschließlich an Benutzer weitergegeben, die vom betreuenden Benutzer (Coordinator oder Eigentümer) ausdrücklich Zugang erhalten haben. Eine Weitergabe an Dritte erfolgt grundsätzlich nicht, es sei denn:
          </p>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>Der konfigurierte E-Mail-Dienstleister erhält die E-Mail-Adresse eines eingeladenen Benutzers zum Zweck der Einladungsübermittlung.</li>
            <li>Falls die KI bei einem gehosteten Anbieter läuft, erhält dieser Anbieter den Dokumenteninhalt im Klartext zur KI-Verarbeitung. Ist auch die Bilderkennung dort konfiguriert (<code>VLLM_VISION_URL</code>), erhält er zusätzlich die Seitenbilder des Dokuments selbst, nicht nur den daraus gelesenen Text. Welcher Anbieter das ist, hängt von der Konfiguration dieser Installation ab; auf den vom OpenAvisio-Projekt betriebenen Instanzen ist es die IONOS Cloud GmbH (AI Model Hub, Verarbeitung in Deutschland). In diesem Fall ist ein Auftragsverarbeitungsvertrag (AVV) abzuschließen — eine Vorlage liegt der Software bei (<code>docs/avv-vorlage.md</code>). Läuft die KI lokal (Ollama oder ein eigenes vLLM), verlässt kein Dokumententext diese Installation.</li>
          </ul>
        </section>

        <section className="space-y-3">
          {process.env.UMAMI_URL && (
            <>
              <h2 className="text-lg font-semibold">Reichweitenmessung (Umami)</h2>
              <p>
                Diese Installation nutzt die selbst gehostete Analysesoftware Umami
                ({process.env.UMAMI_URL?.replace("https://", "")}), um die Nutzung der Seite
                statistisch auszuwerten. Umami setzt keine Cookies, erstellt keine
                Nutzerprofile und speichert IP-Adressen nicht; erhoben werden
                ausschließlich anonymisierte, aggregierte Zugriffsdaten (aufgerufene
                Seiten, Browsertyp, Herkunftsland). Die Daten verlassen den Server des
                Betreibers nicht. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO
                (berechtigtes Interesse an der Reichweitenmessung); ein
                Einwilligungsbanner ist mangels Cookies und Profilbildung nicht
                erforderlich.
              </p>
            </>
          )}

          <h2 className="text-lg font-semibold">5. Speicherdauer</h2>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>Patientendaten: bis zur Löschung durch einen Coordinator oder den zuständigen Benutzer (Recht auf Löschung nach Art. 17 DSGVO)</li>
            <li>Benutzerdaten: bis zur Löschung des Benutzerkontos</li>
            <li>Anwendungsprotokolle: 30 Tage</li>
            <li>Sitzungstokens: 15 Minuten (Zugriffstoken), 7 Tage (Refresh-Token)</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">6. Ihre Rechte</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Sie haben gegenüber dem Verantwortlichen folgende Rechte:
          </p>
          <ul className="text-sm space-y-2 list-disc list-inside text-muted-foreground">
            <li><strong>Auskunft (Art. 15 DSGVO)</strong> — Sie können jederzeit eine vollständige Kopie Ihrer gespeicherten Daten anfordern (FHIR-Export verfügbar).</li>
            <li><strong>Berichtigung (Art. 16 DSGVO)</strong> — Sie können unrichtige Daten korrigieren lassen.</li>
            <li><strong>Löschung (Art. 17 DSGVO)</strong> — Sie können die vollständige und unwiderrufliche Löschung aller Ihrer Daten verlangen.</li>
            <li><strong>Datenübertragbarkeit (Art. 20 DSGVO)</strong> — Sie können Ihre Daten in einem maschinenlesbaren Format (FHIR R4 JSON) erhalten.</li>
            <li><strong>Einschränkung der Verarbeitung (Art. 18 DSGVO)</strong> — Sie können unter bestimmten Voraussetzungen die Einschränkung der Verarbeitung verlangen.</li>
            <li><strong>Widerspruch (Art. 21 DSGVO)</strong> — Sie können der Verarbeitung Ihrer Daten widersprechen.</li>
          </ul>
          <p className="text-sm text-muted-foreground">
            Zur Ausübung Ihrer Rechte wenden Sie sich an: <strong>[KONTAKT-E-MAIL]</strong>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">7. Beschwerderecht</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Sie haben das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren. Für Baden-Württemberg ist dies:
          </p>
          <div className="text-sm text-muted-foreground">
            <p className="font-medium">Der Landesbeauftragte für den Datenschutz und die Informationsfreiheit Baden-Württemberg (LfDI)</p>
            <p>Lautenschlagerstraße 20, 70173 Stuttgart</p>
            <p>Telefon: +49 711 61 55 41-0</p>
            <p>Website: <a href="https://www.baden-wuerttemberg.datenschutz.de" className="underline" target="_blank" rel="noopener noreferrer">www.baden-wuerttemberg.datenschutz.de</a></p>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">8. Datensicherheit</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Alle Dokumente werden verschlüsselt gespeichert (AES-GCM mit individuellem Schlüssel je Dokument). Die Übertragung erfolgt ausschließlich über HTTPS. Der Zugriff auf Patientendaten ist auf ausdrücklich berechtigte Benutzer beschränkt. Alle Datenänderungen werden protokolliert.
          </p>
        </section>

        <div className="pt-4 border-t text-xs text-muted-foreground">
          Diese Datenschutzerklärung gilt für die OpenAvisio-Installation unter <strong>[DOMAIN]</strong>.
          Stand: Juni 2026.
        </div>
      </div>
    </div>
  );
}
