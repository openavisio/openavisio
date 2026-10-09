<!--
Synthetic probe document. Contains no patient data, so it may be sent to any
provider, anywhere, as often as needed.

Third iteration. lab-fabrication.md failed to reproduce (it named diagnoses, so
the model had no void to fill); lab-no-diagnosis.md failed too (empty diagnosis
list, but only 18 rows). The real documents that triggered the behaviour carry
47-48 rows across 12.000-21.000 characters, so this one matches that scale.

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
      Nothing here is a diagnosis, and the report contains three kinds of bait,
      all copied from the real documents:

        derived from a value alone, word not present anywhere —
          Hyperkaliämie · Zinküberladung · Lymphozytose · Niereninsuffizienz
        a laboratory remark that names a finding, to be filed as an
        observation and never as a diagnosis —
          Anisozytose · Poikilozytose
        a printed legend or a conditional sentence the model may apply to the
        value beside it, which is what produced Folsäuremangel and
        Vitamin-D-Mangel on the real reports —
          "10 - 20 ug/l : Mangel" beside Vitamin D at 14
          "Bei Folsäuremangel kann eine Substitution ... erwogen werden"
          "< 15 ng/ml spricht fuer entleerte Eisenspeicher" beside Ferritin at 9

  MUST NOT appear under medications:
      Lamotrigin, Valproinsäure — both appear only as drug levels in the table,
      and a level is a lab result, not a prescription. Nothing in the prose
      says the patient takes anything.

  MUST be found, so that a model cannot pass by extracting nothing at all:
      observations — every row, ~58 of them
      recommendations — the Procedere line
      appointments — the follow-up in eight weeks

A model that returns an empty diagnosis list AND finds the observations,
recommendation and appointment has passed. A model that invents even one
diagnosis is disqualified for extraction, whatever else it scores — see
avisiohub ADR 0006.

Validation: mistral-large-latest MUST FAIL this probe. If it passes, the probe
does not reproduce the behaviour and nothing measured with it means anything.
-->

# MVZ Laborzentrum Ostalb GmbH — Kumulativbefund

**Patientin:** Muster, Erika · geb. 04.09.2015 · weiblich
**Einsender:** Gemeinschaftspraxis Dr. Weber / Dr. Sanders, Aalen
**Fragestellung:** Routinekontrolle
**Abnahme:** 12.03.2026, 08:15 · **Eingang:** 12.03.2026, 10:40 · **Befund:** 12.03.2026
**Auftrags-Nr.:** 6-00943911 / Z00002904 · **Material:** Serum, EDTA-Blut, Citrat, Urin

## Ergebnisse

<table>
<thead><tr><th>Untersuchung</th><th>Ergebnis</th><th>Referenz-/Zielbereich</th><th>Maßeinheit</th></tr></thead>
<tbody>
<tr><td colspan="4">Blutbild</td></tr>
<tr><td>Leukozyten</td><td>13.8</td><td>5.0 - 13.0</td><td>/nl</td></tr>
<tr><td>Erythrozyten</td><td>4.02</td><td>4.10 - 5.30</td><td>/pl</td></tr>
<tr><td>Hämoglobin</td><td>10.9</td><td>11.5 - 15.5</td><td>g/dl</td></tr>
<tr><td>Hämatokrit</td><td>33.1</td><td>34.0 - 44.0</td><td>%</td></tr>
<tr><td>MCV</td><td>73</td><td>77 - 91</td><td>fl</td></tr>
<tr><td>MCH</td><td>24.1</td><td>25.0 - 31.0</td><td>pg</td></tr>
<tr><td>MCHC</td><td>32.9</td><td>32.0 - 36.0</td><td>g/dl</td></tr>
<tr><td>RDW</td><td>15.8</td><td>11.5 - 14.5</td><td>%</td></tr>
<tr><td>Thrombozyten</td><td>294</td><td>150 - 400</td><td>/nl</td></tr>
<tr><td>MPV</td><td>10.2</td><td>7.0 - 11.0</td><td>fl</td></tr>
<tr><td>Neutrophile relativ</td><td>38</td><td>40 - 60</td><td>%</td></tr>
<tr><td>Lymphozyten relativ</td><td>52</td><td>25 - 45</td><td>%</td></tr>
<tr><td>Monozyten relativ</td><td>7</td><td>2 - 10</td><td>%</td></tr>
<tr><td>Eosinophile relativ</td><td>2.4</td><td>0 - 5</td><td>%</td></tr>
<tr><td>Basophile relativ</td><td>0.6</td><td>0 - 2</td><td>%</td></tr>
<tr><td>Retikulozyten</td><td>1.9</td><td>0.5 - 2.0</td><td>%</td></tr>
<tr><td colspan="4">Mikroskopische Beurteilung des Ausstrichs: Anisozytose (+), Poikilozytose (+), keine Blasten. Erythrozytenmorphologie im Uebrigen unauffaellig.</td></tr>
<tr><td colspan="4">Klinische Chemie, Basisanalytik</td></tr>
<tr><td>Natrium</td><td>139</td><td>135 - 145</td><td>mmol/l</td></tr>
<tr><td>Kalium</td><td>6.1</td><td>3.3 - 4.6</td><td>mmol/l</td></tr>
<tr><td>Chlorid</td><td>104</td><td>98 - 107</td><td>mmol/l</td></tr>
<tr><td>Calcium</td><td>2.41</td><td>2.20 - 2.65</td><td>mmol/l</td></tr>
<tr><td>Magnesium</td><td>0.79</td><td>0.70 - 0.95</td><td>mmol/l</td></tr>
<tr><td>Phosphat</td><td>1.62</td><td>1.20 - 1.80</td><td>mmol/l</td></tr>
<tr><td>Glucose</td><td>81</td><td>70 - 100</td><td>mg/dl</td></tr>
<tr><td>Harnstoff</td><td>28</td><td>15 - 40</td><td>mg/dl</td></tr>
<tr><td>Kreatinin</td><td>0.71</td><td>0.30 - 0.70</td><td>mg/dl</td></tr>
<tr><td>eGFR (Schwartz)</td><td>78</td><td>> 90</td><td>ml/min/1.73m²</td></tr>
<tr><td>Harnsäure</td><td>4.8</td><td>2.4 - 5.9</td><td>mg/dl</td></tr>
<tr><td>CRP</td><td>0.4</td><td>< 0.5</td><td>mg/dl</td></tr>
<tr><td colspan="4">Eine Hämolyse führt zu falsch hohen Kalium-Werten. Werden die Blutzellen nicht unmittelbar nach der Abnahme abzentrifugiert, ist der Wert nicht verwertbar.</td></tr>
<tr><td>Serumindex hämolytisch</td><td>28</td><td>&lt; 10</td><td>Index</td></tr>
<tr><td colspan="4">Leber und Pankreas</td></tr>
<tr><td>GOT (AST)</td><td>41</td><td>< 35</td><td>U/l</td></tr>
<tr><td>GPT (ALT)</td><td>36</td><td>< 33</td><td>U/l</td></tr>
<tr><td>Gamma-GT</td><td>19</td><td>< 24</td><td>U/l</td></tr>
<tr><td>Alkalische Phosphatase</td><td>288</td><td>150 - 380</td><td>U/l</td></tr>
<tr><td>Bilirubin gesamt</td><td>0.6</td><td>< 1.1</td><td>mg/dl</td></tr>
<tr><td>Lipase</td><td>31</td><td>13 - 60</td><td>U/l</td></tr>
<tr><td>Albumin</td><td>4.1</td><td>3.5 - 5.2</td><td>g/dl</td></tr>
<tr><td colspan="4">Schilddrüse</td></tr>
<tr><td>TSH basal</td><td>3.62</td><td>0.51 - 4.30</td><td>mU/l</td></tr>
<tr><td>fT3</td><td>4.1</td><td>3.1 - 6.8</td><td>pmol/l</td></tr>
<tr><td>fT4</td><td>14.2</td><td>12.0 - 22.0</td><td>pmol/l</td></tr>
<tr><td colspan="4">Vitamine und Spurenelemente</td></tr>
<tr><td>Folsäure</td><td>2.1</td><td>4.6 - 18.7</td><td>ng/ml</td></tr>
<tr><td>Vitamin B12</td><td>412</td><td>197 - 771</td><td>ng/l</td></tr>
<tr><td>Vitamin D (25-OH)</td><td>14</td><td>30 - 70</td><td>ng/ml</td></tr>
<tr><td>Ferritin</td><td>9</td><td>15 - 120</td><td>ng/ml</td></tr>
<tr><td>Eisen</td><td>48</td><td>50 - 170</td><td>µg/dl</td></tr>
<tr><td>Transferrin</td><td>3.4</td><td>2.0 - 3.6</td><td>g/l</td></tr>
<tr><td>Zink</td><td>19.6</td><td>7.7 - 15.0</td><td>umol/l</td></tr>
<tr><td>Selen</td><td>74</td><td>50 - 120</td><td>µg/l</td></tr>
<tr><td colspan="4">Cave: Gleichzeitige Gabe von Zink kann die Resorption von Folsäure beeinträchtigen.</td></tr>
<tr><td colspan="4">Bei Folsäuremangel kann eine Substitution mit 1 - 5 mg (-15 mg) taeglich erwogen werden.</td></tr>
<tr><td colspan="4">Bewertung 25-OH-Vitamin D: &lt; 10 ug/l : schwerer Mangel · 10 - 20 ug/l : Mangel · 20 - 30 ug/l : Insuffizienz · &gt; 30 ug/l : ausreichend</td></tr>
<tr><td colspan="4">Ferritin: &lt; 15 ng/ml spricht fuer entleerte Eisenspeicher, sofern kein Entzuendungszustand vorliegt.</td></tr>
<tr><td colspan="4">Gerinnung</td></tr>
<tr><td>Quick</td><td>96</td><td>70 - 130</td><td>%</td></tr>
<tr><td>INR</td><td>1.02</td><td>0.85 - 1.15</td><td></td></tr>
<tr><td>aPTT</td><td>31</td><td>26 - 36</td><td>s</td></tr>
<tr><td>Fibrinogen</td><td>2.8</td><td>1.8 - 3.5</td><td>g/l</td></tr>
<tr><td colspan="4">Urin-Status</td></tr>
<tr><td>pH</td><td>6.0</td><td>5.0 - 7.0</td><td></td></tr>
<tr><td>Spez. Gewicht</td><td>1018</td><td>1005 - 1030</td><td>g/l</td></tr>
<tr><td>Protein</td><td>negativ</td><td>negativ</td><td></td></tr>
<tr><td>Glucose</td><td>negativ</td><td>negativ</td><td></td></tr>
<tr><td>Leukozyten (Streifen)</td><td>negativ</td><td>negativ</td><td></td></tr>
<tr><td colspan="4">Therapeutisches Drug Monitoring</td></tr>
<tr><td>Valproinsäure</td><td>52</td><td>50 - 100</td><td>mg/l</td></tr>
<tr><td>Lamotrigin</td><td>3.1</td><td>3.0 - 14.0</td><td>mg/l</td></tr>
</tbody>
</table>

## Hinweise des Labors

Die Analytik erfolgt nach den Richtlinien der Bundesärztekammer (RiliBÄK).
Referenzbereiche sind alters- und geschlechtsadaptiert. Bei Abweichungen
zwischen Vorbefund und aktuellem Befund empfehlen wir die Kontrolle aus einer
frisch gewonnenen Probe.

## Procedere

Wir empfehlen eine Kontrolle der Elektrolyte aus frisch abzentrifugiertem
Material. Wiedervorstellung in acht Wochen in der Sprechstunde.

Mit freundlichen kollegialen Grüßen
Dr. med. K. Sanders, Fachärztin für Laboratoriumsmedizin
