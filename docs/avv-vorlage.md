# Auftragsverarbeitungsvertrag (AVV) — Vorlage

**Keine Rechtsberatung.** Diese Vorlage nach Art. 28 DSGVO deckt den Regelfall
ab; sie ersetzt keine anwaltliche Prüfung. Die Datenschutzerklärung von
OpenAvisio verlangt einen AVV, lieferte aber keinen — diese Lücke schließt dieses
Dokument (#112).

## Wann Sie einen AVV brauchen

Nur dann, wenn ein **Dritter** in Ihrem Auftrag personenbezogene Daten
verarbeitet. Bei OpenAvisio ist das genau in diesen Fällen so:

| Konstellation | AVV nötig? |
|---|---|
| Sie hosten selbst, KI läuft lokal (Ollama/vLLM auf eigener Hardware) | **Nein.** Niemand außer Ihnen verarbeitet die Daten. |
| Sie hosten selbst, KI bei einem gehosteten Anbieter (`VLLM_URL` zeigt auf den Anbieter) | **Ja**, mit diesem Anbieter — der Dokumenteninhalt verlässt Ihr Haus, bei dort konfigurierter Bilderkennung (`VLLM_VISION_URL`) auch die Seitenbilder selbst. Aktuell in Gebrauch: IONOS Cloud GmbH (AI Model Hub, auf den vom Projekt betriebenen Instanzen). Achtung: die **IONOS Cloud GmbH** ist ein anderer Vertragspartner als die **IONOS SE**, mit eigenem AVV und eigener Unterauftragnehmerliste. Wer den falschen benennt, benennt den falschen. |
| Ihr Server steht bei einem Hoster (Hetzner, Netcup …) | **Ja**, mit dem Hoster. Die meisten stellen einen fertigen AVV bereit. |
| Ein Dienstleister betreibt die Installation für Sie | **Ja**, mit diesem Dienstleister. |
| Sie betreiben es rein privat für die eigene Familie | **Nein.** Die DSGVO greift für die reine Haushaltstätigkeit nicht (Art. 2 Abs. 2 lit. c). |

Der wichtigste Satz zuerst: **Wenn Sie selbst hosten und die KI lokal läuft,
brauchen Sie gar nichts.** Genau dafür ist OpenAvisio gebaut.

---

## Vertrag zur Auftragsverarbeitung

zwischen

**Verantwortlicher** (Auftraggeber)
_Name, Anschrift_

und

**Auftragsverarbeiter** (Auftragnehmer)
_Name, Anschrift_

### 1. Gegenstand und Dauer

Der Auftragnehmer verarbeitet personenbezogene Daten im Auftrag des
Verantwortlichen im Rahmen der Nutzung von OpenAvisio. Die Verarbeitung endet
mit Beendigung des zugrunde liegenden Hauptvertrags.

### 2. Art und Zweck der Verarbeitung

_Zutreffendes eintragen, z. B.:_ Bereitstellung von Server-Infrastruktur /
Verarbeitung von Dokumententext durch ein KI-Sprachmodell zur Extraktion
strukturierter Angaben.

### 3. Art der Daten und Kategorien betroffener Personen

- **Datenarten:** Gesundheitsdaten (**besondere Kategorie**, Art. 9 DSGVO),
  Stammdaten der betreuten Person, Kontaktdaten der betreuenden Personen,
  Nutzungs- und Protokolldaten.
- **Betroffene:** die betreute Person (häufig ein Kind), betreuende Angehörige,
  Nutzerinnen und Nutzer der Installation.

Da Gesundheitsdaten verarbeitet werden, gelten **erhöhte Anforderungen**. Ein
Auftragnehmer, der das nicht ausdrücklich zusichert, ist ungeeignet.

### 4. Weisungsbindung

Der Auftragnehmer verarbeitet die Daten ausschließlich auf dokumentierte Weisung
des Verantwortlichen. Hält er eine Weisung für rechtswidrig, teilt er dies
unverzüglich mit.

### 5. Vertraulichkeit

Der Auftragnehmer verpflichtet die mit der Verarbeitung befassten Personen zur
Vertraulichkeit (Art. 28 Abs. 3 lit. b DSGVO).

### 6. Technische und organisatorische Maßnahmen (Art. 32 DSGVO)

Der Auftragnehmer trifft geeignete Maßnahmen, insbesondere:

- Verschlüsselung bei Übertragung und Speicherung
- Zugriffskontrolle, Protokollierung von Zugriffen
- Verfahren zur regelmäßigen Überprüfung der Wirksamkeit
- Wiederherstellbarkeit nach einem Zwischenfall

_Die Maßnahmen des Auftragnehmers sind als Anlage beizufügen._

**Zur Einordnung:** OpenAvisio selbst verschlüsselt Dokumente, extrahierten Text
und Chunks mit einem Schlüssel je Patient (ADR-031). Ein Auftragnehmer sieht
also — je nach Konstellation — nur Chiffrat. **Ausnahme:** Bei
einem gehosteten KI-Anbieter (`VLLM_URL` zeigt auf den Anbieter) erhält der
KI-Dienst den **Klartext** des Dokuments. Das ist der Grund für den AVV, und der
Grund, warum die lokale KI der Regelfall ist. Ein eigenes vLLM ist kein Dritter
und braucht keinen AVV, auch wenn es mit einem Schlüssel abgesichert ist.

Betroffen sind je nach Konfiguration **alle drei Rollen**: die Textauswertung,
die Bilderkennung (`VLLM_VISION_URL`, sendet die Seitenbilder) und die
Einbettungen (`VLLM_EMBED_URL`, sendet die Textabschnitte). Jede lässt sich
einzeln bei einer lokalen Ollama belassen; `OLLAMA_VISION_URL` und
`OLLAMA_EMBED_URL` haben Vorrang vor den gehosteten Gegenstücken.

### 7. Unterauftragsverhältnisse

Der Einsatz weiterer Auftragsverarbeiter bedarf der vorherigen Genehmigung des
Verantwortlichen. Bestehende Unterauftragnehmer sind in einer Anlage zu benennen.

### 8. Unterstützungspflichten

Der Auftragnehmer unterstützt den Verantwortlichen bei der Beantwortung von
Betroffenenanfragen (Art. 15–22 DSGVO), bei Meldungen von Datenschutzverletzungen
(Art. 33, 34) und bei Datenschutz-Folgenabschätzungen (Art. 35).

### 9. Löschung und Rückgabe

Nach Abschluss der Verarbeitung löscht der Auftragnehmer alle personenbezogenen
Daten oder gibt sie zurück, nach Wahl des Verantwortlichen. Bestehende
Aufbewahrungspflichten bleiben unberührt.

### 10. Nachweise und Kontrollen

Der Auftragnehmer stellt dem Verantwortlichen alle erforderlichen Informationen
zum Nachweis der Einhaltung zur Verfügung und ermöglicht Überprüfungen.

---

_Ort, Datum_ — _Unterschrift Verantwortlicher_ — _Unterschrift Auftragnehmer_

---

## Hinweis zu Drittstaaten

Verarbeitet ein Auftragnehmer außerhalb der EU/des EWR, sind zusätzlich
Standardvertragsklauseln und eine Übermittlungs-Folgenabschätzung erforderlich.
Für Gesundheitsdaten ist davon dringend abzuraten. Der derzeit verwendete
Anbieter, die IONOS Cloud GmbH, verarbeitet in Deutschland. Die Cloud-Nutzung
bleibt trotzdem eine bewusste Entscheidung des Betreibers. Tragen Sie in
die Anlage nach Abschnitt 7 den Anbieter ein, den **Ihre** Installation
tatsächlich benutzt.
