#!/usr/bin/env python3
"""Wandelt comdirect-Finanzreports (PDF, 2020-2026) in eine Sure-Finance-CSV um.

Die Finanzreports haben linksbündige Tabellenspalten, deren Positionen nicht im
Text-Matrix-, sondern im Grafik-Matrix-Operator stehen. Deshalb lesen wir die
Textpositionen aus der kombinierten Text- x Grafik-Matrix statt sie pypdf
"raten" zu lassen.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from bisect import bisect_right
from datetime import datetime
from pathlib import Path

from pandas import DataFrame, isna
from pypdf import PdfReader

# --- PDF-Texte ---------------------------------------------------------------
# Die Finanzreport-PDFs sind in Windows-1252 kodiert.
PDF_ENCODING = "cp1252"

# --- comdirect-Tabellenlayout -------------------------------------------------
# Abschnittstitel (Teilstrings), die wir auswerten, abgebildet auf den
# Kontonamen in der Sure-CSV. Visa-Umsätze landen im Girokonto.
ACCOUNT_TITLES = ("Girokonto", "Tagesgeld", "Visa")
ACCOUNT_OUTPUT = {"Girokonto": "Girokonto", "Tagesgeld": "Tagesgeld", "Visa": "Girokonto"}

# Spalten, die wir aus einer Finanzreport-Tabelle lesen. Die Kopfzeilen
# "Auftraggeber/Empfänger" bzw. "Ausgang"/"Eingang" werden als Teilstrings erkannt.
DATA_HEADERS = ("Buchungstag", "Vorgang", "Auftraggeber", "Buchungstext", "Ausgang")
IGNORED_SUBHEADERS = ("Valuta", "Umsatztag")
REGEX_DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

# IBAN/BIC teilt sich die x-Position mit der Empfängerspalte und wird deshalb
# in diese hineingezogen. Wir schneiden sie (samt BIC) wieder ab.
REGEX_IBANBIC = re.compile(
    r"(?P<sender>.+?) (?P<ibanbic>[A-Z]{2}\d{2}[A-Z0-9]+ [A-Z]{6}[A-Z0-9]{5})"
)

# --- Sure-CSV ----------------------------------------------------------------
SURE_HEADERS = ("date*", "amount*", "name", "currency", "category", "tags", "account", "notes")
CURRENCY = "EUR"


def parse_finanzreport(fp, verbose: bool = False) -> dict[str, DataFrame]:
    """Liest alle Kontotabellen aus einem Finanzreport-PDF.

    Rückgabe: {Abschnittstitel: DataFrame} mit den Spalten aus DATA_HEADERS.
    """
    ACCOUNT_END_1 = "Neuer"
    ACCOUNT_END_2 = "Saldo"
    TITLE_FONT_SIZE = 9      # >= dieser Größe = Abschnittstitel
    MIN_FONT_SIZE = 3        # kleiner = unlesbarer Text, wird ignoriert
    LINE_BREAK_THRESHOLD = 12.01  # darunter = Zeilenumbruch in einer Tabellenzeile
    LAST_HEADER_LEEWAY = 10  # die letzte (Betrags-)Spalte ist rechtsbündig

    account_tables = {t: DataFrame() for t in ACCOUNT_TITLES}
    header_x = {t: [] for t in ACCOUNT_TITLES}       # sortierte x-Positionen
    header_name = {t: {} for t in ACCOUNT_TITLES}    # x-Position -> Spaltenname
    seen_headers: list[str] = []

    active = ""
    first_header = 0.0
    prev_col = 0.0
    cur_row = 0
    cur_row_y = 1e7  # y ist invertiert (0 = unterer Rand)
    first_col_line_breaks_y = 0.0
    row_without_date = True
    end_signal_seen = False

    def is_table_header(text: str) -> bool:
        return any(h in text for h in DATA_HEADERS)

    def header_for(text: str) -> str:
        return next(h for h in DATA_HEADERS if h in text)

    def closest_header(text_x: float, coords: list[float]) -> float | None:
        i = bisect_right(coords, text_x)
        return None if i == 0 else coords[i - 1]

    def is_date(text: str) -> bool:
        return REGEX_DATE.fullmatch(text) is not None

    def is_line_break(y: float, prev_y: float) -> bool:
        return (prev_y - y) < LINE_BREAK_THRESHOLD

    def cell(table: DataFrame, row: int, col: str) -> str | None:
        if col in table.columns and row in table.index:
            return table.at[row, col]
        return None

    def on_text(operator, operands, cm_matrix, tm_matrix):
        nonlocal active, first_header, prev_col, cur_row, cur_row_y
        nonlocal first_col_line_breaks_y, row_without_date, end_signal_seen
        if operator not in (b"TJ", b"Tj"):
            return
        raw = operands[0][0] if operator == b"TJ" else operands[0]
        text = raw.decode(PDF_ENCODING)
        font_size = tm_matrix[0]
        if font_size < MIN_FONT_SIZE:
            return
        # Position aus der kombinierten Text- x Grafik-Matrix.
        x = tm_matrix[4] * cm_matrix[0] + tm_matrix[5] * cm_matrix[2] + cm_matrix[4]
        y = tm_matrix[4] * cm_matrix[1] + tm_matrix[5] * cm_matrix[3] + cm_matrix[5]

        # Kontotitel erkennen (beginnt eine neue Tabelle)
        if font_size > TITLE_FONT_SIZE and any(t in text for t in ACCOUNT_TITLES):
            active = next(t for t in ACCOUNT_TITLES if t in text)
            first_header = 0.0
            prev_col = 0.0
            cur_row = 0
            cur_row_y = 1e7
            first_col_line_breaks_y = 0.0
            row_without_date = True
            seen_headers.clear()
            return
        if not active:
            return

        table = account_tables[active]
        coords = header_x[active]

        # Kopfzeile: x-Positionen der Spalten registrieren
        if is_table_header(text):
            hx = x - LAST_HEADER_LEEWAY if DATA_HEADERS[-1] in text else x
            if hx not in coords and text not in seen_headers:
                coords.append(hx)
                coords.sort()
                header_name[active][hx] = header_for(text)
                seen_headers.append(text)
            if DATA_HEADERS[0] in text:
                first_header = hx
                cur_row_y = y
            return

        column = closest_header(x + LAST_HEADER_LEEWAY, coords)
        if column is None or y > cur_row_y:
            return  # außerhalb der Tabelle oder Seitenkopf

        # Tabellenende ("Neuer Saldo")
        if text == ACCOUNT_END_1:
            end_signal_seen = True
            return
        if end_signal_seen and text == ACCOUNT_END_2:
            active = ""
            end_signal_seen = False
            return
        end_signal_seen = False

        # Zeilenanfang = Buchungstag in der ersten Spalte
        if column == first_header:
            if is_line_break(y, first_col_line_breaks_y):
                # zweites Datum der Zeile (Valuta) -- nur zur Kontrolle
                first_col_line_breaks_y = y
                if verbose and text not in IGNORED_SUBHEADERS and text != cell(
                    table, cur_row, header_name[active][column]
                ):
                    print(f"Hinweis: Wertstellung {text} weicht vom Buchungstag ab.")
                return
            if not is_date(text):
                row_without_date = True
                return
            cur_row += 1
            cur_row_y = first_col_line_breaks_y = y
            row_without_date = False
        if row_without_date:
            return

        col_name = header_name[active][column]
        if column == prev_col and cell(table, cur_row, col_name) is not None:
            table.loc[cur_row, col_name] = f"{table.loc[cur_row, col_name]} {text}"
        else:
            table.loc[cur_row, col_name] = text
        prev_col = column

    reader = PdfReader(fp, strict=True)
    for page in reader.pages:
        page.extract_text(visitor_operand_before=on_text)

    for title, table in account_tables.items():
        if not table.empty:
            table = table.reindex(columns=list(DATA_HEADERS))
            account_tables[title] = table.astype(object).where(table.notna(), "")
    return account_tables


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _clean_amount(raw) -> str:
    """' +4.000,00' -> '4000.00', '-231,53' -> '-231.53'."""
    value = _text(raw).replace(".", "").replace(",", ".")
    return value[1:] if value.startswith("+") else value


def _to_iso(date_str) -> str:
    return datetime.strptime(_text(date_str), "%d.%m.%Y").strftime("%Y-%m-%d")


def _clean_name(payee, fallback) -> str:
    match = REGEX_IBANBIC.match(_text(payee))
    name = match.group("sender") if match else _text(payee)
    return name or _text(fallback)


def table_to_sure_rows(df: DataFrame, account: str) -> list[list[str]]:
    rows = []
    for _, record in df.iterrows():
        try:
            date = _to_iso(record["Buchungstag"])
        except ValueError:
            continue
        amount = _clean_amount(record["Ausgang"])
        if not amount:
            continue
        name = _clean_name(record["Auftraggeber"], record["Buchungstext"])
        notes = " | ".join(
            part for part in (_text(record["Buchungstext"]), _text(record["Vorgang"])) if part
        )
        rows.append([date, amount, name, CURRENCY, "", "", account, notes])
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Wandelt comdirect-Finanzreports (PDF, 2020-2026) in eine Sure-Finance-CSV um."
    )
    parser.add_argument(
        "-p", "--path",
        help="Ordner mit den Finanzreport-PDFs (Standard: aktuelles Verzeichnis, rekursiv)",
    )
    parser.add_argument(
        "-o", "--out", default="sure-import.csv",
        help='Ausgabedatei (Standard: "sure-import.csv")',
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="zusätzliche Hinweise ausgeben")
    args = parser.parse_args(argv)

    in_dir = Path(args.path) if args.path else Path.cwd()
    if not in_dir.is_absolute():
        in_dir = Path.cwd() / in_dir

    files = sorted(in_dir.glob("**/*Finanzreport*.pdf"))
    if not files:
        print(f"Keine Finanzreport-PDFs in {in_dir} gefunden.", file=sys.stderr)
        return 1

    rows: list[list[str]] = []
    for fp in files:
        for title, df in parse_finanzreport(fp, verbose=args.verbose).items():
            if df.empty:
                continue
            account = ACCOUNT_OUTPUT[title]
            print(f"{fp.name}: {len(df)} Umsätze in {title} -> {account}")
            rows.extend(table_to_sure_rows(df, account))

    if not rows:
        print("Keine Umsätze gefunden.", file=sys.stderr)
        return 1

    rows.sort(key=lambda row: (row[0], row[6]))
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(SURE_HEADERS)
        writer.writerows(rows)
    print(f"{len(rows)} Umsätze nach {args.out} geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
