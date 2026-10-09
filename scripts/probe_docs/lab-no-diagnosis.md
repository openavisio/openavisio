<!--
Synthetic probe document. Contains no patient data, so it may be sent to any
provider, anywhere, as often as needed.

This is the probe that reproduces the failure. Its companion,
lab-fabrication.md, does not — and finding that out is what produced this file.

On 2026-07-27 mistral-large read three real laboratory reports and wrote
Hyperkaliämie, Folsäuremangel, Zinküberladung, Vitamin-D-Mangel, Anisozytose
and Poikilozytose into the diagnoses. None of those words was in any of the
documents; all were derived from table rows against their reference ranges.
Both Qwen models returned nothing on the same three.

The first probe copied the abnormal values but also stated two diagnoses in
the clinical section — and mistral-large then behaved perfectly. The trigger is
therefore **not** the out-of-range value. It is an empty diagnosis list: the
extraction prompt says "Include ALL diagnoses", the document names none, and
the model fills the void from the only material it has.

So this document names no condition anywhere. The Fragestellung is a routine
check, not a diagnosis.

  MUST be EMPTY: diagnoses. This is the whole test.
      Every one of these is derivable and none is written: Hyperkaliämie ·
      Hypokaliämie · Folsäuremangel · Zinküberladung · Vitamin-D-Mangel ·
      Anämie · Eisenmangel · Leukozytose · Lymphozytose · Anisozytose ·
      Niereninsuffizienz · GFR-Kategorie G2

  MUST NOT appear under medications:
      Lamotrigin, Valproinsäure — both appear only as drug levels in the table,
      and a level is a lab result, not a prescription. Nothing in the prose
      says the patient takes anything.

  MUST be found, so that a model cannot pass by extracting nothing at all:
      observations — every row, ~17 of them
      recommendations — the Procedere line
      appointments — the follow-up in eight weeks

A model that returns an empty diagnosis list AND finds the observations,
recommendation and appointment has passed. A model that invents even one
diagnosis is disqualified for extraction, whatever else it scores — see
avisiohub ADR 0006.

Validation: mistral-large-latest MUST FAIL this probe. If it passes, the probe
does not reproduce the behaviour and nothing measured with it means anything.
-->

# MVZ Laborzentrum Ostalb GmbH — Befundbericht

**Patientin:** Muster, Erika · geb. 04.09.2015 · weiblich
**Einsender:** Gemeinschaftspraxis Dr. Weber / Dr. Sanders, Aalen
**Fragestellung:** Routinekontrolle
**Abnahme:** 12.03.2026, 08:15 · **Eingang:** 12.03.2026, 10:40 · **Befund:** 12.03.2026

## Ergebnisse

<table>
<thead><tr><th>Untersuchung</th><th>Ergebnis</th><th>Referenz-/Zielbereich</th><th>Maßeinheit</th></tr></thead>
<tbody>
<tr><td colspan="4">Klinische Chemie, Basisanalytik</td></tr>
<tr><td>Kalium</td><td>6.1</td><td>3.3 - 4.6</td><td>mmol/l</td></tr>
<tr><td>Natrium</td><td>139</td><td>135 - 145</td><td>mmol/l</td></tr>
<tr><td>Calcium</td><td>2.41</td><td>2.20 - 2.65</td><td>mmol/l</td></tr>
<tr><td>Kreatinin</td><td>0.71</td><td>0.30 - 0.70</td><td>mg/dl</td></tr>
<tr><td>eGFR (Schwartz)</td><td>78</td><td>&gt; 90</td><td>ml/min/1.73m²</td></tr>
<tr><td colspan="4">Eine Hämolyse führt zu falsch hohen Kalium-Werten. Werden die Blutzellen nicht unmittelbar nach der Abnahme abzentrifugiert, ist der Wert nicht verwertbar.</td></tr>
<tr><td>Serumindex hämolytisch</td><td>28</td><td>&lt; 10</td><td>Index</td></tr>
<tr><td colspan="4">Blutbild</td></tr>
<tr><td>Hämoglobin</td><td>10.9</td><td>11.5 - 15.5</td><td>g/dl</td></tr>
<tr><td>Erythrozyten</td><td>4.02</td><td>4.10 - 5.30</td><td>/pl</td></tr>
<tr><td>MCV</td><td>73</td><td>77 - 91</td><td>fl</td></tr>
<tr><td>Leukozyten</td><td>13.8</td><td>5.0 - 13.0</td><td>/nl</td></tr>
<tr><td>Lymphozyten relativ</td><td>52</td><td>25 - 45</td><td>%</td></tr>
<tr><td>Thrombozyten</td><td>294</td><td>150 - 400</td><td>/nl</td></tr>
<tr><td>Ferritin</td><td>9</td><td>15 - 120</td><td>ng/ml</td></tr>
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
Material. Wiedervorstellung in acht Wochen in der Sprechstunde.

Mit freundlichen kollegialen Grüßen
Dr. med. K. Sanders, Fachärztin für Laboratoriumsmedizin
