#!/usr/bin/env python3
"""Generate the 7 synthetic demo PDFs for Lena Hoffmann.

Uses weasyprint (already a backend dependency). Run from the repo root:
  python scripts/generate_demo_pdfs.py

Output: docs/demo/01_gp_referral.pdf … 07_supplier_invoice.pdf
Commit the generated files so they are available for manual upload in local dev
and for the seed script on the demo instance.
"""

import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "demo"

try:
    from weasyprint import HTML
except ImportError:
    print("weasyprint not found — run: pip install weasyprint", file=sys.stderr)
    sys.exit(1)

_CSS = """
  body { font-family: Arial, sans-serif; font-size: 10pt; margin: 2cm; color: #222; }
  .letterhead { border-bottom: 2px solid #1a5276; padding-bottom: 8px; margin-bottom: 16px; }
  .letterhead h1 { font-size: 14pt; margin: 0 0 2px; color: #1a5276; }
  .letterhead p  { margin: 0; font-size: 9pt; color: #555; }
  .meta { margin-bottom: 16px; font-size: 9pt; }
  h2 { font-size: 11pt; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  td, th { border: 1px solid #ccc; padding: 4px 8px; font-size: 9pt; }
  th { background: #eaf0f6; }
  .label { font-weight: bold; }
  .signature { margin-top: 32px; border-top: 1px solid #aaa; padding-top: 8px; font-size: 9pt; }
  .ref { font-size: 8pt; color: #888; margin-top: 24px; }
"""


def pdf(filename: str, html_body: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_html = f"<html><head><style>{_CSS}</style></head><body>{html_body}</body></html>"
    out = OUTPUT_DIR / filename
    HTML(string=full_html).write_pdf(str(out))
    print(f"  {out}")


def main() -> None:
    print(f"Generating demo PDFs → {OUTPUT_DIR}")

    # 1. GP Referral Letter
    pdf("01_gp_referral.pdf", """
      <div class="letterhead">
        <h1>Hausarztpraxis Dr. Schmidt</h1>
        <p>Hauptstraße 12 · 80331 München · Tel: +49 89 12345-0</p>
      </div>
      <div class="meta">
        <p><span class="label">Datum:</span> 10. März 2024</p>
        <p><span class="label">An:</span> St. Marien-Kinderklinik, Abteilung für Neuropädiatrie</p>
        <p><span class="label">Betreff:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
      </div>
      <h2>Überweisung zur neurologischen Abklärung</h2>
      <p>Sehr geehrte Kollegin, sehr geehrter Kollege,</p>
      <p>wir überweisen unsere Patientin <strong>Lena Hoffmann</strong> (geboren am
      14. Mai 2019, weiblich) zur neuropädiatrischen Abklärung nach zwei fraglichen
      generalisierten tonisch-klonischen Anfallsereignissen.</p>
      <p>Das erste Ereignis trat am <strong>15. Januar 2024</strong> auf, dauerte
      circa 2 Minuten und wurde von der Mutter Anna Hoffmann beobachtet. Lena war
      während des Ereignisses nicht ansprechbar und anschließend für circa
      10 Minuten postiktal. Ein zweites Ereignis mit ähnlicher Symptomatik trat am
      <strong>28. Februar 2024</strong> auf. Im Intervall ist Lena neurologisch
      unauffällig bei altersgerechter Entwicklung.</p>
      <h2>Anamnese</h2>
      <table>
        <tr><th>Punkt</th><th>Angabe</th></tr>
        <tr><td>Aktuelle Medikation</td><td>Keine</td></tr>
        <tr><td>Epilepsie in der Familienanamnese</td><td>Nicht bekannt</td></tr>
        <tr><td>Kürzlicher fieberhafter Infekt</td><td>Keiner</td></tr>
        <tr><td>Entwicklung</td><td>Altersentsprechend</td></tr>
      </table>
      <h2>Beurteilung und Fragestellung</h2>
      <p>Verdacht auf kindliche Epilepsie. Wir bitten um zeitnahe Durchführung
      eines EEG sowie um eine klinisch-neurologische Untersuchung. Bitte vergeben
      Sie einen neuropädiatrischen Vorstellungstermin für Lena.</p>
      <div class="signature">
        <p>Mit freundlichen kollegialen Grüßen<br>Dr. Klaus Schmidt<br>Hausarztpraxis Dr. Schmidt</p>
      </div>
      <p class="ref">Ref: SCH-2024-0310-LH</p>
    """)

    # 2. EEG Report
    pdf("02_eeg_report.pdf", """
      <div class="letterhead">
        <h1>St. Marien-Kinderklinik — Abteilung für Neuropädiatrie</h1>
        <p>Funktionsdiagnostik / Neurodiagnostik · Marienplatz 1 · 80331 München · Tel: +49 89 98765-200</p>
      </div>
      <div class="meta">
        <p><span class="label">Patientin:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
        <p><span class="label">Befunddatum:</span> 2. April 2024</p>
        <p><span class="label">Zuweisender Arzt:</span> Dr. K. Schmidt</p>
        <p><span class="label">Befundende Ärztin:</span> Dr. M. Weber</p>
      </div>
      <h2>Elektroenzephalogramm (EEG) — Befundbericht</h2>
      <h2>Befund</h2>
      <p>Standard-EEG mit 20 Elektroden im Wachzustand und im Schlaf (insgesamt
      45 Minuten). Der Grundrhythmus zeigt eine okzipital betonte Alpha-Aktivität
      von 8–9 Hz, altersentsprechend. Im Wachzustand zeigen sich
      <strong>bilateral synchrone 3-Hz-Spike-Wave-Komplexe</strong>, akzentuiert
      bei Schläfrigkeit, mit einer Dauer von 3–8 Sekunden. Kein Herdbefund.
      Keine photoparoxysmale Reaktion.</p>
      <h2>Beurteilung</h2>
      <p><strong>Pathologisches EEG.</strong> Der Befund ist vereinbar mit einer
      <strong>Absence-Epilepsie des Kindesalters (CAE)</strong>. Das interiktale
      Muster und die klinische Anamnese sind typisch. Der Beginn wird anhand des
      ersten berichteten Ereignisses auf den 15. Januar 2024 geschätzt.</p>
      <h2>Empfehlungen</h2>
      <ul>
        <li>Beginn einer antikonvulsiven Therapie — Valproat wird als Mittel der
            ersten Wahl bei CAE empfohlen.</li>
        <li>Wiedervorstellung in der neuropädiatrischen Ambulanz in 3 Monaten zur
            Beurteilung des Therapieansprechens.</li>
        <li>Eltern wurden zur Ersten Hilfe bei Anfällen und zur Information der
            Schule beraten.</li>
      </ul>
      <div class="signature">
        <p>Dr. M. Weber, Oberärztin Neuropädiatrie<br>St. Marien-Kinderklinik</p>
      </div>
      <p class="ref">Ref: SMH-NEURO-2024-0402 · EEG-LH-24001</p>
    """)

    # 3. Neurology Follow-up
    pdf("03_neurology_followup.pdf", """
      <div class="letterhead">
        <h1>St. Marien-Kinderklinik — Abteilung für Neuropädiatrie</h1>
        <p>Neuropädiatrische Ambulanz · Marienplatz 1 · 80331 München</p>
      </div>
      <div class="meta">
        <p><span class="label">Patientin:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
        <p><span class="label">Vorstellungsdatum:</span> 15. Juli 2024</p>
        <p><span class="label">Behandelnde Ärztin:</span> Dr. M. Weber</p>
        <p><span class="label">Kopie an Hausarzt:</span> Dr. K. Schmidt</p>
      </div>
      <h2>Neuropädiatrische Verlaufskontrolle — 3-Monats-Kontrolle</h2>
      <p>Sehr geehrte Kollegin, sehr geehrter Kollege,</p>
      <p>wir berichten über Lena, die sich heute 3 Monate nach Beginn der
      Valproat-Therapie (Beginn 15. April 2024) zur Verlaufskontrolle
      vorstellte. Die Mutter Anna Hoffmann berichtet über
      <strong>keine weiteren Anfallsereignisse</strong> seit Therapiebeginn.</p>
      <h2>Untersuchungsbefund</h2>
      <table>
        <tr><th>Parameter</th><th>Wert</th><th>Referenz</th></tr>
        <tr><td>Körpergewicht</td><td>22.0 kg</td><td>25.–50. Perzentile (5 Jahre)</td></tr>
        <tr><td>Körpergröße</td><td>119 cm</td><td>50.–75. Perzentile (5 Jahre)</td></tr>
        <tr><td>Neurologischer Status</td><td>Unauffällig</td><td>—</td></tr>
        <tr><td>Berichtete Nebenwirkungen</td><td>Keine</td><td>—</td></tr>
      </table>
      <h2>Aktuelle Medikation</h2>
      <table>
        <tr><th>Wirkstoff</th><th>Dosis</th><th>Einnahmeschema</th><th>Beginn</th></tr>
        <tr><td>Valproat</td><td>300 mg/Tag</td>
            <td>150 mg morgens, 150 mg abends</td><td>15. April 2024</td></tr>
      </table>
      <h2>Procedere</h2>
      <ul>
        <li>Valproat 300 mg/Tag fortführen — sehr gutes frühes Ansprechen.</li>
        <li>Blutentnahme in 6 Monaten: Valproat-Serumspiegel, Leberwerte,
            Blutbild.</li>
        <li>Wiedervorstellung in 6–12 Monaten, bei erneuten Anfällen früher.</li>
      </ul>
      <div class="signature">
        <p>Dr. M. Weber, Oberärztin Neuropädiatrie<br>St. Marien-Kinderklinik · 15. Juli 2024</p>
      </div>
      <p class="ref">Ref: SMH-NEURO-2024-0715</p>
    """)

    # 4. Blood Panel
    pdf("04_blood_panel.pdf", """
      <div class="letterhead">
        <h1>Zentrallabor Nordbaden</h1>
        <p>Laborstraße 5 · 80636 München · Tel: +49 89 55500-0</p>
      </div>
      <div class="meta">
        <p><span class="label">Patientin:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
        <p><span class="label">Probenentnahme:</span> 20. Januar 2025</p>
        <p><span class="label">Befundausgang:</span> 20. Januar 2025</p>
        <p><span class="label">Einsenderin:</span> Dr. M. Weber, St. Marien-Kinderklinik</p>
      </div>
      <h2>Laborbefund — Kontrolle unter antikonvulsiver Therapie</h2>
      <table>
        <tr>
          <th>Untersuchung</th><th>Ergebnis</th><th>Einheit</th>
          <th>Referenzbereich</th><th>Bewertung</th>
        </tr>
        <tr>
          <td>Valproat-Spiegel (Serum)</td><td>75.0</td>
          <td>mcg/mL</td><td>50–100</td><td>Therapeutisch</td>
        </tr>
        <tr>
          <td>ALT (GPT)</td><td>18</td>
          <td>U/L</td><td>7–45</td><td>Normal</td>
        </tr>
        <tr>
          <td>AST (GOT)</td><td>22</td>
          <td>U/L</td><td>10–40</td><td>Normal</td>
        </tr>
        <tr>
          <td>Leukozyten</td><td>6.8</td>
          <td>10⁹/L</td><td>4.5–13.5</td><td>Normal</td>
        </tr>
        <tr>
          <td>Hämoglobin</td><td>12.4</td>
          <td>g/dL</td><td>11.5–15.5</td><td>Normal</td>
        </tr>
      </table>
      <h2>Zusammenfassung</h2>
      <p>Der Valproat-Spiegel liegt im therapeutischen Bereich. Leberwerte und
      Blutbild sind unauffällig. Kein pathologischer Befund. Kontrolle in
      6 Monaten empfohlen.</p>
      <div class="signature">
        <p>Dr. S. Braun, Fachärztin für Laboratoriumsmedizin<br>Zentrallabor Nordbaden · 20. Januar 2025</p>
      </div>
      <p class="ref">Ref: CML-2025-0120-LH · Accession: 25-LAB-00418</p>
    """)

    # 5. School Health Check
    pdf("05_school_health_check.pdf", """
      <div class="letterhead">
        <h1>Schulärztlicher Dienst Grundschule Am Fluss</h1>
        <p>Schulstraße 8 · 80333 München · Tel: +49 89 33300-0</p>
      </div>
      <div class="meta">
        <p><span class="label">Patientin:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
        <p><span class="label">Untersuchungsdatum:</span> 8. September 2025</p>
        <p><span class="label">Einschulung:</span> 1. Klasse, Grundschule Am Fluss</p>
        <p><span class="label">Schulgesundheitsfachkraft:</span> K. Fischer, Gesundheits- und Kinderkrankenpflegerin</p>
      </div>
      <h2>Jährliche Gesundheitsuntersuchung — Einschulung 1. Klasse</h2>
      <h2>Anthropometrische Messwerte</h2>
      <table>
        <tr><th>Parameter</th><th>Wert</th><th>Perzentile</th></tr>
        <tr><td>Körpergewicht</td><td>24.5 kg</td><td>50. (6 Jahre)</td></tr>
        <tr><td>Körpergröße</td><td>123 cm</td><td>50.–75. (6 Jahre)</td></tr>
        <tr><td>BMI</td><td>16.2 kg/m²</td><td>Normbereich</td></tr>
      </table>
      <h2>Screening-Ergebnisse</h2>
      <table>
        <tr><th>Untersuchung</th><th>Ergebnis</th></tr>
        <tr><td>Visus — rechtes Auge</td><td>6/6 (normal)</td></tr>
        <tr><td>Visus — linkes Auge</td><td>6/6 (normal)</td></tr>
        <tr><td>Hörscreening (beidseits)</td><td>Bestanden</td></tr>
        <tr><td>Farbsehen</td><td>Normal</td></tr>
      </table>
      <h2>Anamnese (Elternangaben)</h2>
      <p>Lenas Mutter berichtet, dass Lena unter Valproat-Therapie bei
      Absence-Epilepsie des Kindesalters derzeit gut eingestellt ist. In den
      letzten 12 Monaten keine Anfälle. Die Schule ist über die Diagnose
      informiert. Die Entwicklung ist altersentsprechend: Sprache, Feinmotorik,
      Grobmotorik und soziale Entwicklung unauffällig.</p>
      <h2>Entwicklungs-Meilenstein</h2>
      <p>Einschulung mit 6 Jahren und 3 Monaten — im erwarteten Bereich.
      Dokumentierter Meilenstein: Einschulung (1. Klasse, September 2025).</p>
      <h2>Empfehlungen</h2>
      <p>Bei der Einschulungsuntersuchung keine Auffälligkeiten. Routinemäßige
      Verlaufskontrollen empfohlen. Das Schulpersonal wurde über das Vorgehen
      zur Ersten Hilfe bei Anfällen instruiert.</p>
      <div class="signature">
        <p>K. Fischer, Gesundheits- und Kinderkrankenpflegerin<br>Schulärztlicher Dienst Grundschule Am Fluss · 8. September 2025</p>
      </div>
      <p class="ref">Ref: RPS-HEALTH-2025-0908-LH</p>
    """)

    # 6. Hospital Discharge Summary
    pdf("06_hospital_discharge.pdf", """
      <div class="letterhead">
        <h1>St. Marien-Kinderklinik</h1>
        <p>Station für Neuropädiatrie · Marienplatz 1 · 80331 München</p>
      </div>
      <div class="meta">
        <p><span class="label">Patientin:</span> Lena Hoffmann, geb. 14. Mai 2019 (w)</p>
        <p><span class="label">Aufnahme:</span> 12. Februar 2026</p>
        <p><span class="label">Entlassung:</span> 14. Februar 2026</p>
        <p><span class="label">Behandelnde Ärztin:</span> Dr. M. Weber, Neuropädiatrie</p>
        <p><span class="label">Kopie an Hausarzt:</span> Dr. K. Schmidt</p>
      </div>
      <h2>Entlassungsbericht — Durchbruchanfall</h2>
      <h2>Aufnahmegrund</h2>
      <p>Sehr geehrte Kollegin, sehr geehrter Kollege,</p>
      <p>wir berichten über Lena, die am 12. Februar 2026 nach einem beobachteten
      <strong>generalisierten tonisch-klonischen Durchbruchanfall</strong> zu Hause
      stationär aufgenommen wurde. Das Ereignis dauerte circa
      <strong>3 Minuten</strong> und sistierte spontan. Postiktale Phase von
      15 Minuten. Keine Verletzungen.</p>
      <h2>Anamnese</h2>
      <p>Absence-Epilepsie des Kindesalters, EEG-gesichert im April 2024. Seit
      April 2024 Dauertherapie mit Valproat 300 mg/Tag. Letzte anfallsfreie
      Periode: circa 22 Monate vor dieser Aufnahme.</p>
      <h2>Untersuchungsergebnisse</h2>
      <p>Blutentnahme bei Aufnahme: Valproat-Spiegel 52 mcg/mL (niedrig-therapeutischer
      Bereich, vereinbar mit dem Längenwachstum der letzten Monate). Leberwerte
      unauffällig. Im EEG vermehrte Spike-Wave-Aktivität im Vergleich zur
      Voraufzeichnung.</p>
      <h2>Therapie und Medikationsänderung</h2>
      <table>
        <tr><th>Wirkstoff</th><th>Bisherige Dosis</th><th>Neue Dosis</th><th>Gültig ab</th></tr>
        <tr>
          <td>Valproat</td><td>300 mg/Tag</td>
          <td>400 mg/Tag (200 mg morgens, 200 mg abends)</td><td>14. Februar 2026</td>
        </tr>
      </table>
      <h2>Entlassungsplan</h2>
      <ul>
        <li>Entlassung unter Valproat <strong>400 mg/Tag</strong> in zwei
            Einzeldosen, gültig ab 14. Februar 2026.</li>
        <li>Ambulante neuropädiatrische Kontrolle vereinbart für den
            <strong>14. März 2026</strong>.</li>
        <li>Bei erneuten Anfällen vor dem Kontrolltermin bitte umgehende
            Kontaktaufnahme mit der Neuropädiatrie.</li>
        <li>Die Schule wurde über die Dosisanpassung informiert.</li>
      </ul>
      <div class="signature">
        <p>Dr. M. Weber, Oberärztin Neuropädiatrie<br>
        St. Marien-Kinderklinik · 14. Februar 2026</p>
      </div>
      <p class="ref">Ref: SMH-PAED-NEURO-2026-0214 · Ward: 4B</p>
    """)

    # 7. Supplier invoice — the document the Expenses feature reads an amount from
    pdf("07_supplier_invoice.pdf", """
      <div class="letterhead">
        <h1>Sanitätshaus Berger GmbH</h1>
        <p>Lindenweg 4 · 80331 München · Tel: +49 89 55512-0 · USt-IdNr. DE812345678</p>
      </div>
      <div class="meta">
        <p><span class="label">Rechnungsnummer:</span> 2026-04-1187</p>
        <p><span class="label">Rechnungsdatum:</span> 18. April 2026</p>
        <p><span class="label">Kundin:</span> Anna Hoffmann, für Lena Hoffmann, geb. 14.05.2019</p>
        <p><span class="label">Leistungszeitraum:</span> April 2026</p>
      </div>

      <h2>Rechnung</h2>
      <table>
        <tr><th>Pos.</th><th>Bezeichnung</th><th>Menge</th><th>Einzelpreis</th><th>Betrag</th></tr>
        <tr><td>1</td><td>Bettschutzeinlagen, waschbar (Pflegehilfsmittel)</td><td>2</td><td>12,50 €</td><td>25,00 €</td></tr>
        <tr><td>2</td><td>Einmalhandschuhe, Box à 100 Stück</td><td>1</td><td>8,90 €</td><td>8,90 €</td></tr>
        <tr><td>3</td><td>Händedesinfektion 500 ml</td><td>1</td><td>6,10 €</td><td>6,10 €</td></tr>
      </table>

      <table>
        <tr><td class="label">Zwischensumme</td><td>40,00 €</td></tr>
        <tr><td class="label">enthaltene MwSt. 19 %</td><td>6,39 €</td></tr>
        <tr><td class="label">Gesamtbetrag</td><td><strong>40,00 €</strong></td></tr>
      </table>

      <p>Zahlbar ohne Abzug bis zum 2. Mai 2026 auf das unten genannte Konto.
         Bitte geben Sie die Rechnungsnummer als Verwendungszweck an.</p>
      <p>Pflegehilfsmittel zum Verbrauch nach § 40 Abs. 2 SGB XI. Ein Antrag auf
         Kostenübernahme kann bei der Pflegekasse eingereicht werden.</p>

      <div class="signature">
        <p>Sanitätshaus Berger GmbH · Geschäftsführer: T. Berger<br>
        IBAN DE02 1203 0000 0000 2020 51 · Amtsgericht München HRB 998877</p>
      </div>
      <p class="ref">Rechnung 2026-04-1187 · Kundennummer 44 021</p>
    """)

    # 8. Pflegekasse decision — the document the Widerspruch deadline reads (ADR 041).
    # Partial rejection on purpose: Pflegegrad 2 where 3 was applied for prints as an
    # approval, which is exactly why the trigger is the Rechtsbehelfsbelehrung and not
    # a judgement about the outcome.
    pdf("08_pflegekasse_decision.pdf", """
      <div class="letterhead">
        <h1>Pflegekasse bei der AOK Baden-Württemberg</h1>
        <p>Presselstraße 19 · 70191 Stuttgart · Tel: +49 711 2593-0</p>
      </div>
      <div class="meta">
        <p><span class="label">Bescheid vom:</span> 12. Mai 2026</p>
        <p><span class="label">Aktenzeichen:</span> PK-2026-88431</p>
        <p><span class="label">Versicherte:</span> Lena Hoffmann, geb. 14.05.2019</p>
        <p><span class="label">Antragstellerin:</span> Anna Hoffmann (gesetzliche Vertreterin)</p>
      </div>

      <h2>Bescheid über die Einstufung in einen Pflegegrad</h2>
      <p>Sehr geehrte Frau Hoffmann,</p>
      <p>auf Ihren Antrag vom 3. März 2026 auf Einstufung in den Pflegegrad 3 haben wir
         das Gutachten des Medizinischen Dienstes vom 28. April 2026 ausgewertet.</p>
      <p>Wir stellen fest: Ab dem 1. Juni 2026 besteht ein Anspruch auf Leistungen nach
         <strong>Pflegegrad 2</strong>. Der beantragte Pflegegrad 3 wird abgelehnt.</p>

      <table>
        <tr><th>Modul</th><th>Gewichtete Punkte</th></tr>
        <tr><td>Modul 1 &ndash; Mobilität</td><td>5,0</td></tr>
        <tr><td>Modul 2 &ndash; Kognitive und kommunikative Fähigkeiten</td><td>7,5</td></tr>
        <tr><td>Modul 3 &ndash; Verhaltensweisen und psychische Problemlagen</td><td>3,75</td></tr>
        <tr><td>Modul 4 &ndash; Selbstversorgung</td><td>20,0</td></tr>
        <tr><td>Modul 5 &ndash; Bewältigung von Krankheits- und Therapieanforderungen</td><td>5,0</td></tr>
        <tr><td>Modul 6 &ndash; Gestaltung des Alltagslebens und sozialer Kontakte</td><td>5,0</td></tr>
        <tr><td class="label">Gesamtpunktzahl (gewichtet)</td><td class="label">42,5</td></tr>
      </table>

      <h2>Begründung</h2>
      <p>Mit 42,5 gewichteten Punkten wird die für Pflegegrad 3 erforderliche Punktzahl von
         47,5 nicht erreicht. Der Hilfebedarf im Bereich der Selbstversorgung bleibt hinter
         dem im Antrag geschilderten Umfang zurück. Die im Antrag geschilderte nächtliche
         Beaufsichtigung wurde im Modul 5 berücksichtigt. Eine schwere Beeinträchtigung der
         Selbständigkeit im Sinne des § 15 Abs. 3 Nr. 3 SGB XI liegt nach dem Gutachten
         nicht vor.</p>

      <h2>Rechtsbehelfsbelehrung</h2>
      <p>Gegen diesen Bescheid kann innerhalb eines Monats nach Bekanntgabe Widerspruch
         erhoben werden. Der Widerspruch ist schriftlich oder zur Niederschrift bei der
         Pflegekasse bei der AOK Baden-Württemberg, Presselstraße 19, 70191 Stuttgart,
         einzulegen.</p>

      <div class="signature">
        <p>Pflegekasse bei der AOK Baden-Württemberg<br>
        Abteilung Leistungen · Sachbearbeitung: M. Kellner</p>
      </div>
      <p class="ref">Aktenzeichen PK-2026-88431 · Bescheid vom 12.05.2026</p>
    """)

    print("Done.")


if __name__ == "__main__":
    main()
