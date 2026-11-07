# Plan: comdirect Finanzreport → Sure Finance CSV import

## Ziel

Dieses Repository soll comdirect-Finanzreports (PDF) einlesen und direkt eine
**Sure-Finance-CSV** im Importformat erzeugen. Das Skript wird dabei deutlich
vereinfacht, die Abhängigkeit von conda/miniforge entfällt.

Unterstützter PDF-Zeitraum: **2020–2026**.

## Entscheidungen (aus dem Review)

| # | Thema | Entscheidung |
|---|-------|--------------|
| Q1 | Ausgabe | Alte deutsche CSV ersetzen; **nur** noch Sure-Format. |
| Q2 | Parser | Interna nicht neu schreiben, aber nötige Fixes (siehe unten). |
| Q3 | Umfang | Girokonto + Visa + Tagesgeld parsen; **keine Kategorisierung**. |
| Q4 | Bibliotheken | pandas behalten; numpy-Import entfernen. |
| Q5 | Umgebung | **uv** + `pyproject.toml`; `environment.yml` löschen. |
| Q6 | Struktur | Alles in **ein Skript** flach zusammenführen. |
| Q7 | Plattform | plattformübergreifend, **UTF-8**; `bin/run-default.bat` löschen. |
| Q8 | Sprache | Deutsch für README/Konsole/Kommentare. |
| Q9 | Verifikation | Echte (redigierte) Samples: 2020 + 2026 im Repo. |
| Q10 | Upload | Nur CSV, kein API-Upload. |
| Q11/R6 | Betrag | Vorzeichen unverändert übernehmen (`-` = Ausgabe), "+" entfernen. |
| Q12/R4 | `name` | `Auftraggeber/Empfänger`, sonst `Buchungstext`. |
| Q13/R5 | `notes` | `Buchungstext \| Vorgang`, **ohne** Dateinamen. |
| Q14/Q20 | Konten | Konten per Teilstring-Titel erkennen. |
| Q15 | Überträge | Alle Zeilen ausgeben; Sure matcht Überträge selbst. |
| Q16 | Ausgabe | Komma, UTF-8, volle Sure-Kopfzeile, leer `category`/`tags`, `currency=EUR`, nach Datum sortiert, Default `sure-import.csv`. |
| Q17 | CLI | `-p/--path` (rekursiv) und `-o/--out`. |
| Q21 | Visa | **Kein** eigenes Visa-Konto; Visa-Umsätze gehen ins **Girokonto** (ab 2020). |
| Q22 | Legacy | Code für Formate < 2020 entfernen; Hinweis im README. |
| Q23 | Konten final | Nur **Girokonto** und **Tagesgeld**. Depot und Verrechnungskonto werden **ignoriert**. |
| Q24 | Texttexte | Rohtext unverändert lassen (keine "Wortreparatur"). |
| Q25 | Betrag/Name | IBAN/BIC aus `name` herausschneiden. |
| Q26 | `notes` | Trenner `" | "`, Reihenfolge `Buchungstext | Vorgang`. |
| Q27 | Konsole | Pro-Zeile-`Info:`-Meldungen nur mit `-v`; kurze Zusammenfassung bleibt. |

## Erkenntnisse aus den Samples (Fakten)

- 2020-Sample: 9-Spalten-Layout (Buchungstag, Valuta, Vorgang, Referenz,
  Auftraggeber/Empfänger, IBAN/BIC, Buchungstext, Ausgang, Eingang), Konten
  Girokonto / TagesgeldPLUS-Konto / Visa Prepaid-Karte.
- 2026-Sample: **gleiches** Layout; nur Girokonto + Tagesgeld mit Umsätzen,
  Visa-Debitkarte erscheint innerhalb des Girokontos.
- Beträge mit Vorzeichen, deutsches Zahlenformat (`-231,53`, `+4.000,00`).
- Die ursprüngliche Parser-Version scheitert an beiden Dateien.
- Erwartete Extraktion: 2020 → 2 Girokonto-Umsätze; 2026 → 48 Girokonto + 4 Tagesgeld.

## Nötige Parser-Fixes (verifiziert)

1. **Koordinaten**: Positionen liegen in der Grafik-Matrix (`cm`), nicht in der
   Text-Matrix (`tm`), die der Parser liest. → Position aus `tm × cm` bilden:
   `x = tm[4]*cm[0] + tm[5]*cm[2] + cm[4]`, analog `y`.
2. **Spalten pro Konto**: `seen_header_texts` ist global und verhindert, dass
   das zweite Konto seine Spalten registriert. → bei neuem Kontotitel leeren.
3. **Kontotitel**: Titel sind über mehrere Text-Chunks verteilt
   ("Tagesgeld" + "PLUS-Konto"). → Teilstrings `Girokonto`, `Tagesgeld`, `Visa`.
4. **Spaltenzuordnung ohne Hacks**: Spalten über x-Position → logischer Name
   zuordnen (statt sortierter Position + "4-Spalten-Visa-Hack").
5. **Legacy entfernen**: `Tf`-Fontgröße (2014), `"Neuer Saldo"` als Einzel-Chunk,
   4-Spalten-Visa-Hack, `A29.11.2019`-Datumsfix. Toten Code
   (`out_of_account_parts`, `unassignable_parts`, `get_parsing_error`) entfernen.

## Ausgabemapping → Sure-CSV

Kopfzeile: `date*,amount*,name,currency,category,tags,account,notes`

| Sure-Spalte | Quelle |
|-------------|--------|
| `date*` | `Buchungstag` `TT.MM.JJJJ` → `JJJJ-MM-TT` |
| `amount*` | `Ausgang`: Tausender-`.` weg, `,`→`.`, führendes `+` weg |
| `name` | `Auftraggeber` ohne IBAN/BIC, sonst `Buchungstext` |
| `currency` | fest `EUR` |
| `category` | leer (Kategorien später in Sure) |
| `tags` | leer |
| `account` | `Girokonto` bzw. `Tagesgeld` (Visa → Girokonto) |
| `notes` | `Buchungstext \| Vorgang` |

Sortierung: nach Datum, dann Konto. Datei: komma-getrennt, UTF-8.

## Dateien

**Neu**
- `comdirect_to_sure.py` – einziges Skript (Parser + Mapping + CLI)
- `pyproject.toml` – Abhängigkeiten `pandas`, `pypdf`; `[tool.uv] package = false`
- `PLAN.md` – dieses Dokument

**Geändert**
- `README.md` – deutsche Anleitung mit `uv`, Hinweis auf 2020–2026,
  Disclaimer zu entfernten Legacy-Formaten, Beschreibung der Sure-CSV.
- `.gitignore` – generierte `sure-import.csv` ignorieren.

**Gelöscht**
- `environment.yml` (conda)
- `bin/run-default.bat` (Windows-Wrapper)
- `parse-kontoauszug/` (`__init__.py`, `__main__.py`, `base.py`, `comdirect.py`)
- `readme/` (veraltete Screenshots der alten CSV-Ausgabe)

**Behalten, aber untracked** (per `.gitignore` ausgeschlossen)
- Die beiden Sample-PDFs und `transaction_sample.csv` bleiben lokal liegen,
  gehören aber nicht ins Repo.

## Verifikation

1. `uv run comdirect_to_sure.py -v` gegen die beiden PDFs im Repo ausführen.
2. Erwartung: 2020 → 2 Zeilen, 2026 → 52 Zeilen (48 + 4), Summe 54.
3. Kopfzeile und Stichproben prüfen (Datum ISO, Betrag `-231.53`, Konto korrekt,
   `notes`-Format, Umlaute in UTF-8).
4. Sicherstellen, dass Depot/Verrechnungskonto ignoriert werden.

## Offene Risiken

- Reale Reports mit **Tagesgeld-/Visa-Bewegungen** außerhalb der Samples sind
  nicht verifiziert (Sample-Tagesgeld hat 4 Zeilen; Visa-Tabellen sind leer).
- Pre-2020-Formate werden bewusst **nicht** mehr unterstützt (README-Disclaimer).
- Sure dedupliziert nur eingeschränkt; überlappende PDFs können Duplikate erzeugen.

## Umsetzungsstand

- [x] `comdirect_to_sure.py` erstellt (Parser-Fixes + Mapping + CLI)
- [x] `pyproject.toml` (uv) erstellt
- [x] `environment.yml`, `bin/run-default.bat`, `parse-kontoauszug/` entfernt
- [x] `README.md` neu geschrieben (2020–2026, Legacy-Disclaimer)
- [x] `.gitignore` aktualisiert
- [x] Verifikation: 2020 → 2 Zeilen, 2026 → 48 (Girokonto) + 4 (Tagesgeld) = 54 Zeilen;
      CSV valide (UTF-8, 8 Spalten, ISO-Datum, betragsformat geprüft)

Zur Kenntnis:

- `uv` hat `uv.lock` und `.venv/` erzeugt; `.venv/` ist ignoriert, `uv.lock`
  gehört ins Repo.
- Die beiden PDF-Samples und `transaction_sample.csv` sind noch untracked.
- Separate Visa-/Tagesgeld-Tabellen mit echten Umsätzen (über die Samples
  hinaus) sind nicht verifiziert.
