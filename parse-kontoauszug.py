import argparse
from os import getcwd
from pathlib import Path
from typing import Union
from pandas import DataFrame, to_numeric, concat
from parsers.comdirect import get_parsing_error, parse_finanzreport
from numpy import nan

ACCOUNT_TITLES = ("Girokonto", "Visa-Karte")
TABLE_HEADERS = ("Buchungstag", "Vorgang", "Auftraggeber", "Buchungstext", "Ausgang")
IGNORED_SUBHEADERS = ("Valuta", "Umsatztag")
PRINT_HEADERS = ("Buchungstag (orig)", "Vorgang (orig)", "Auftraggeber (orig)", "Buchungstext (orig)", "Ausgang/Eingang (orig)")
ENCODING = "cp1252"
END_WORD = "(?:[^a-zA-Z]|$)"
CATEGORY_REGEX = [
    ("Vorgang (orig)", r"(?i:wertpapiere)", "Depot", "Kauf / Verkauf"),
    ("Vorgang (orig)", r"(?i:Termingeld)", "Depot", "Kauf / Verkauf"),
    ("Vorgang (orig)", r"(?:Bar)", "Einkommen", "Bargeldeinzahlung"),
    ("Vorgang (orig)", r"(?i:auszahlung gaa)|(?i:barauszahlung)", "Sonstige Ausgaben", "Bargeldauszahlung"),
    ("Auftraggeber-Name", r"comdirect Visa", "Ausschließen", "Interner Übertrag"),
    ("Auftraggeber-Name", r"(?i:stadtwerke)|(?i:abfall)", "Wohnen", "Nebenkosten"),
    ("Auftraggeber-Name", r"(?i:kaufland)|(?i:lidl)|(?i:aldi)|(?i:rewe)|(?i:penny)|(?i:edeka)|(?i:tegut)", "Lebenshaltung", "Lebensmittel"),
    ("Auftraggeber-Name", r"(?i:drogeriemarkt)|(?i:rossmann)", "Lebenshaltung", "Drogerie"),
    ("Auftraggeber-Name", r"(?i:deichmann)|(?i:c\+a)", "Lebenshaltung", "Kleidung / Schuhe"),
    ("Auftraggeber-Name", rf"(?i:obi{END_WORD})|(?i:bauhaus{END_WORD})", "Lebenshaltung", "Heim / Garten"),
    ("Auftraggeber-Name", r"(?i:apotheke)", "Lebenshaltung", "Medikamente"),
    ("Auftraggeber-Name", r"(?i:db vertrieb)|(?i:deutsche bahn)|(?i:rnv)", "Verkehrsmittel", "Öffentliche Verkehrsmittel"),
    ("Auftraggeber-Name", r"(?:OIL)", "Verkehrsmittel", "Auto / Tanken"),
    ("Auftraggeber-Name", r"(?i:unitymedia)|(?i:vodafone)|(?i:telefonica)|(?i:drillisch)|(?i:congstar)", "Digital", "Internet / Telefon"),
    ("Auftraggeber-Name", r"(?i:rundfunk)", "Digital", "Rundfunksteuer"),
    ("Auftraggeber-Name", rf"(?i:mcdonalds)|(?i:kfc{END_WORD})|(?i:nordsee gmbh)|(?i:moschmosch)|(?i:gastronomie)|(?i:restaurant)", "Freizeit", "Gastronomie"),
    ("Auftraggeber-Name", r"(?i:cineplex)|(?i:filmpalast)", "Freizeit", "Unterhaltung / Kino / Kultur"),
    ("Auftraggeber-Name", r"(?i:germanwings)", "Reisen", "Flug / Bahn / Bus / Taxi"),
    ("Auftraggeber-Name", r"(?i:bundesagentur für arbeit)", "Einkommen", "Arbeitslosengeld"),
    ("Buchungsnotiz", r"(?i:darlehen)", "Darlehen", "Tilgung"),
    ("Buchungsnotiz", r"(?i:miete)", "Wohnen", "Miete"),
    ("Buchungsnotiz", r"(?i:nebenkostenabrechnung)", "Wohnen", "Miete"),
    ("Buchungsnotiz", r"(?i:hausgeld)", "Wohnen", "Hausgeld"),
    ("Buchungsnotiz", r"(?i:strom)|(?i:wasser)|(?i:heizung)|(?i:fernwaerme)|(?i:abfall)", "Wohnen", "Nebenkosten"),
    ("Buchungsnotiz", rf"(?i:rewe{END_WORD})", "Lebenshaltung", "Lebensmittel"),
    ("Buchungsnotiz", rf"(?i:zara{END_WORD})|(?i:primark)", "Lebenshaltung", "Kleidung / Schuhe"),
    ("Buchungsnotiz", r"(?i:uebertrag auf)|(?i:tagesgeld)|(?i:ueberweisung auf v\s?isa-kar\s?te)|(?i:summe wochenabrechnung \s?visa)|(?i:summe monatsabrechnung visa)|(?i:Ueberweisung von Girokonto auf Visa-Karte)", "Ausschließen", "Interner Übertrag"),
    ("Buchungsnotiz", rf"(?i:wage{END_WORD})|(?i:salary)|(?i:gehalt)|(?i:lohn)|(?i:bezuege )", "Einkommen", "Gehalt"),
    ("Buchungsnotiz", r"(?i:ertraegnisgutschrift)", "Einkommen", "Sparen / Anlegen"),
    ("Buchungsnotiz", r"(?i:bargeldeinzahlung)", "Einkommen", "Bargeldeinzahlung"),
    ("Buchungsnotiz", r"(?i:bargeldauszahlung)", "Sonstige Ausgaben", "Bargeldauszahlung"),
    ("Buchungsnotiz", r"(?i:apotheke)", "Lebenshaltung", "Medikamente"),
    ("Buchungsnotiz", r"(?i:dbvertrieb)", "Verkehrsmittel", "Öffentliche Verkehrsmittel"), # when paying via Paypal
    ("Buchungsnotiz", r"(?i:ryanair)|(?i:wizz air)|(?i:tarom)|(?i:fluegede)|(?i:lufthansa)", "Reisen", "Flug / Bahn / Bus / Taxi"), # when paying via Paypal
    ("Buchungsnotiz", r"(?i:hotel)", "Reisen", "Hotel / Unterkunft"), # when paying by VISA
    ("Buchungsnotiz", r"(?i:burger king)", "Freizeit", "Gastronomie"),
    ("Buchungsnotiz", r"(?i:theater)|(?i:eventim)|(?i:fkp scorpio)", "Freizeit", "Unterhaltung / Kino / Kultur"), # when paying by VISA
    ("Buchungsnotiz", r"(?i:humblebundl)|(?i:steam\s?games)|(?i:wargaming)", "Freizeit", "Hobbies"), # when paying via Paypal
]

def prettify_and_enrich_finanzreport(table: DataFrame, filename: str, account_title: str):
    REGEX_IBANBIC = "(?P<sender>.+?) (?P<ibanbic>[A-Z]{2}\d{2}[A-Z0-9]+ [A-Z]{6}[A-Z0-9]{5})" # https://stackoverflow.com/questions/21928083/iban-validation-check
    REGEX_REFTEXT = "(?P<manualref>.*?) ?End-to-End-Ref\.:(?P<endref>.*)"

    reordered = table.reindex(sorted(table.columns), axis=1)
    
    headers_map = {}
    for i in range(len(PRINT_HEADERS)):
        headers_map[reordered.columns[i]] = PRINT_HEADERS[i]
    renamed = reordered.rename(columns=headers_map)

    renamed["Dateiname"] = filename
    renamed["Konto"] = account_title

    iban_named_matches: DataFrame = renamed[PRINT_HEADERS[2]].str.extract(REGEX_IBANBIC)
    renamed["Auftraggeber-Name"] = iban_named_matches["sender"].fillna(renamed[PRINT_HEADERS[2]])
    renamed["Auftraggeber-IBAN/BIC"] = iban_named_matches["ibanbic"]

    ref_named_matches: DataFrame = renamed[PRINT_HEADERS[3]].str.extract(REGEX_REFTEXT)
    renamed["Buchungsnotiz"] = ref_named_matches["manualref"].fillna(renamed[PRINT_HEADERS[3]])
    renamed["Buchungsreferenz"] = ref_named_matches["endref"]

    numerified_betrag = renamed[PRINT_HEADERS[4]].str.replace(".","").str.replace(",",".")
    renamed["Betrag (Zahl)"] = to_numeric(numerified_betrag)

    renamed["Kategorie"] = nan
    renamed["Unterkategorie"] = nan
    
    for matchcol, regex, category, subcategory in CATEGORY_REGEX:
        matches = renamed[matchcol].str.contains(regex, na=False)
        renamed["Kategorie"] = renamed["Kategorie"].where(~matches, other=category) # where() replaces False with other m(
        renamed["Unterkategorie"] = renamed["Unterkategorie"].where(~matches, other=subcategory) # where() replaces False with other m(
    
    return renamed

def write_finanzreports(tables: list[DataFrame], outfile: Union["FilePath", "WriteBuffer[bytes]", "WriteBuffer[str]"]):
    print(f"Writing final table from {len(tables)} account tables.")
    table = concat(tables, ignore_index=True)
    table.to_csv(outfile, sep=";", encoding=ENCODING, index=False)
               
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dieses Skript liest Comdirect-Finanzreports im pdf-Format und speichert die Umsätze vom Girokonto in einer CSV-Datei.')
    parser.add_argument('-p',dest='path',type=str,help='Pfad, in dem die Finanzreports liegen (absoluter Pfad oder Unterordner relativ zum Skript)')
    parser.add_argument('-o',dest='out',type=str,help='Ausgabe-Dateiname (Standard "girokonto.csv")')
    args = parser.parse_args()
    
    in_dir = Path(args.path) if args.path else Path(getcwd())
    wd = in_dir if in_dir.is_absolute() else getcwd()/in_dir
    collected_tables = []
    for f in wd.glob("**/Finanzreport*.pdf"):
        table_per_account: dict[str, DataFrame] = parse_finanzreport(f)
        error_message = get_parsing_error(table_per_account, f.name)
        if error_message != "":
            print(error_message)
            continue
        prettified_tables = [
            prettify_and_enrich_finanzreport(table, f.name, account) for account, table in table_per_account.items() if not table.empty
        ]
        [collected_tables.append(table) for table in prettified_tables]
    out_p = args.out if args.out else "girokonto.csv"
    if collected_tables:
        write_finanzreports(collected_tables, out_p)
    else:
        print(f"Could not find or parse any Finanzreport at {wd}")
