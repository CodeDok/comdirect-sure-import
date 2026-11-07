# comdirect Finanzreport → Sure Finance CSV

Dieses Skript liest comdirect-Finanzreports im PDF-Format ein und erzeugt eine
CSV-Datei im Importformat von [Sure](https://sure.am) (Transaction Import).

Übernommen werden Datum, Betrag, Empfänger/Verwendungszweck und das Konto.
Kategorien werden **nicht** gesetzt – diese vergibst du anschließend in Sure.

## Unterstützte Finanzreports

Unterstützt werden Finanzreports **aus den Jahren 2020 bis 2026** (aktuelles
Spaltenlayout mit `Ausgang`/`Eingang`). Ältere Formate von vor 2020 werden
**nicht** unterstützt.

Ausgewertet werden die Konten `Girokonto` und `Tagesgeld`. Umsätze der
Visa-Debitkarte werden dem Girokonto zugeordnet; `Depot` und
`Verrechnungskonto` werden ignoriert.

## Voraussetzungen

[uv](https://docs.astral.sh/uv/) – oder alternativ Python ≥ 3.10 mit den
Paketen `pandas` und `pypdf`.

## Ausführung

```
uv run comdirect_to_sure.py
```

Standardmäßig werden im aktuellen Ordner (rekursiv) alle PDF-Dateien gesucht,
deren Name `Finanzreport` enthält, und die Umsätze nach `sure-import.csv`
geschrieben.

Optionen:

| Option | Bedeutung |
|--------|-----------|
| `-p, --path` | Ordner mit den Finanzreport-PDFs (Standard: aktueller Ordner) |
| `-o, --out` | Ausgabedatei (Standard: `sure-import.csv`) |
| `-v, --verbose` | zusätzliche Hinweise ausgeben (z. B. abweichende Wertstellung) |

Beispiel:

```
uv run comdirect_to_sure.py -p "~/Kontoauszüge" -o "girokonto-2020-2026.csv"
```

Ohne uv:

```
pip install pandas pypdf
python comdirect_to_sure.py
```

## Ausgabe

Die CSV ist komma-getrennt und UTF-8-kodiert, die erste Zeile ist die Kopfzeile:

```
date*,amount*,name,currency,category,tags,account,notes
2020-03-18,1486.11,K,EUR,,,Girokonto,End-to-End-Ref.: nicht angegeben | Übertrag / 007/9912
2026-10-02,-231.53,HDI Lebensversicherung AG,EUR,,,Girokonto,HDI Leben/Forderung 10/26 End-to-End-Ref.: 1 CORE / Mandatsref.: M- Gläubiger-ID: DE | Lastschrift / Belastung 2QXN/14665
```

| Spalte | Inhalt |
|--------|--------|
| `date*` | Buchungstag als `JJJJ-MM-TT` |
| `amount*` | Betrag mit Vorzeichen, negativ = Ausgabe |
| `name` | Empfänger/-in, sonst Verwendungszweck |
| `currency` | immer `EUR` |
| `category`, `tags` | leer (in Sure vergeben) |
| `account` | `Girokonto` oder `Tagesgeld` |
| `notes` | Buchungstext und Vorgang |

Die Zeilen sind nach Datum sortiert.

## Import in Sure

1. In Sure **Einstellungen → Importe** öffnen.
2. Die erzeugte CSV hochladen.
3. Im Schritt *Configure* das **Datumsformat `JJJJ-MM-TT`** und die
   Betragsrichtung **„negativ = Ausgabe“** wählen.
4. Im Schritt *Map* die Konten zuordnen: erwartet werden Konten mit den Namen
   `Girokonto` und `Tagesgeld`.

Hinweis: Sure dedupliziert Datei-Importe nur eingeschränkt. Importiere möglichst
überschneidungsfreie Zeiträume.

## Hinweise

- Beträge werden unverändert übernommen (negativ = Ausgabe).
- Durch das PDF-Schriftbild bedingte Wortumbrüche (z. B. `Kartenverfügun g`)
  werden nicht repariert.
- Überträge zwischen `Girokonto` und `Tagesgeld` werden als zwei Zeilen
  ausgegeben; Sure kann sie automatisch als Umbuchung zusammenführen.
