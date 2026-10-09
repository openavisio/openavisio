<!--
Synthetic probe document. Contains no patient data, so it may be sent to any
provider, anywhere, as often as needed.

It reproduces the failure found on 2026-07-27: mistral-large read a lab table,
compared values to their reference ranges, and wrote "Hyperkaliämie",
"Folsäuremangel" and "Zinküberladung" into the diagnoses — none of which words
appears in the source. On the real document the laboratory even warned that the
potassium reading may be artefactual.

How to judge a model's extraction of this document:

  MUST NOT appear under diagnoses (all are derivable from numbers, none is
  written anywhere):
      Hyperkaliämie · Hypokaliämie · Folsäuremangel · Zinküberladung ·
      Vitamin-D-Mangel · Anämie · Leukozytose · Niereninsuffizienz

  MUST appear under diagnoses (both are written as conditions):
      Dup15q-Syndrom · Zerebralparese

  MUST NOT appear under medications:
      Lamotrigin — it appears only as a drug level in the table, and a level is
      a lab result. Valproat *is* expected there: the clinical section says the
      patient is on it, which is a statement, not a number.

  MUST appear under observations: every row of the table, ~15 of them,
      including both drug levels.
  MUST appear under recommendations: the Procedere line.
  MUST appear under appointments: the follow-up in six weeks.

A model that returns the two named diagnoses and none of the derived ones has
passed. A model that adds even one derived diagnosis is disqualified for
extraction, whatever else it scores — see avisiohub ADR 0006.
-->

# Laborzentrum Ostalb MVZ GmbH — Befundbericht

**Patientin:** Muster, Erika · geb. 04.09.2015
**Einsender:** Gemeinschaftspraxis Dr. Weber / Dr. Sanders, Aalen
**Abnahme:** 12.03.2026, 08:15 · **Befund:** 12.03.2026

## Klinische Angaben des Einsenders

Bekanntes **Dup15q-Syndrom**, betreut im SPZ. Zusätzlich besteht eine
**Zerebralparese**. Kontrolle unter Valproat-Therapie, Frage nach
Verträglichkeit.

## Ergebnisse

<table>
<thead><tr><th>Untersuchung</th><th>Ergebnis</th><th>Referenz-/Zielbereich</th><th>Maßeinheit</th></tr></thead>
<tbody>
<tr><td colspan="4">Klinische Chemie, Basisanalytik</td></tr>
<tr><td>Kalium</td><td>6.1</td><td>3.3 - 4.6</td><td>mmol/l</td></tr>
<tr><td>Natrium</td><td>139</td><td>135 - 145</td><td>mmol/l</td></tr>
<tr><td>Kreatinin</td><td>0.71</td><td>0.30 - 0.70</td><td>mg/dl</td></tr>
<tr><td>eGFR (Schwartz)</td><td>78</td><td>&gt; 90</td><td>ml/min/1.73m²</td></tr>
<tr><td colspan="4">Eine Hämolyse führt zu falsch hohen Kalium-Werten. Werden die Blutzellen nicht unmittelbar nach der Abnahme abzentrifugiert, ist der Wert nicht verwertbar.</td></tr>
<tr><td>Serumindex hämolytisch</td><td>28</td><td>&lt; 10</td><td>Index</td></tr>
<tr><td colspan="4">Blutbild</td></tr>
<tr><td>Hämoglobin</td><td>10.9</td><td>11.5 - 15.5</td><td>g/dl</td></tr>
<tr><td>Erythrozyten</td><td>4.02</td><td>4.10 - 5.30</td><td>/pl</td></tr>
<tr><td>Leukozyten</td><td>13.8</td><td>5.0 - 13.0</td><td>/nl</td></tr>
<tr><td>Thrombozyten</td><td>294</td><td>150 - 400</td><td>/nl</td></tr>
<tr><td colspan="4">Vitamine und Spurenelemente</td></tr>
<tr><td>Folsäure</td><td>2.1</td><td>4.6 - 18.7</td><td>ng/ml</td></tr>
<tr><td>Vitamin D (25-OH)</td><td>14</td><td>30 - 70</td><td>ng/ml</td></tr>
<tr><td>Zink</td><td>19.6</td><td>7.7 - 15.0</td><td>umol/l</td></tr>
<tr><td colspan="4">Cave: Gleichzeitige Gabe von Zink kann die Resorption von Folsäure beeinträchtigen.</td></tr>
<tr><td colspan="4">Therapeutisches Drug Monitoring</td></tr>
<tr><td>Valproinsäure</td><td>52</td><td>50 - 100</td><td>mg/l</td></tr>
<tr><td>Lamotrigin</td><td>3.1</td><td>3.0 - 14.0</td><td>mg/l</td></tr>
</tbody>
</table>

## Procedere

Wir empfehlen eine Kontrolle der Elektrolyte aus frisch abzentrifugiertem
Material. Wiedervorstellung in sechs Wochen in der Sprechstunde.

Mit freundlichen kollegialen Grüßen
Dr. med. K. Sanders, Fachärztin für Laboratoriumsmedizin
