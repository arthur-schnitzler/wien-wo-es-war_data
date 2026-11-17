#!/usr/bin/env python3
"""
Erzeugt aus den PMB-Exporten in ./input-data/ (siehe fetch-data-from-pmb.py)

  editions/listevent_YYYY.xml   Ereignisse in Wien, ein TEI-Dokument pro Jahr
  indices/listperson.xml        alle Personen, auf die diese Ereignisse verweisen
                                (inkl. Urheber:innen der aufgeführten Werke)
  indices/listplace.xml         alle Orte der Ereignisse
  indices/listbibl.xml          alle Werke der Ereignisse
  indices/listorg.xml           alle Institutionen der Ereignisse (Veranstalter)

Auswahlkriterien für ein Ereignis:
  * Zeit: Das Ereignis (when-iso bzw. from-iso/to-iso) überschneidet sich mit
    dem Zeitraum START–END. Ereignisse ohne Datum werden verworfen.
  * Ort: Mindestens einer seiner Orte liegt innerhalb der heutigen Wiener
    Stadtgrenze (geodata/wien-landesgrenze.geojson). Maßgeblich sind die
    Koordinaten des Ortes laut PMB-listplace.xml; hat ein Ort keine eigenen
    Koordinaten, werden die der übergeordneten Orte (located_in_place)
    herangezogen, zuletzt die Koordinaten im Ereignis selbst.

Die PMB-Kennungen (person__123, place__123, work__123, org__123, event__123)
werden wie in den anderen Projekten vereinheitlicht zu pmb123.

Nur Python-Standardbibliothek, keine weiteren Abhängigkeiten.
"""

import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date

# --- Konfiguration -----------------------------------------------------------

START = date(1860, 1, 1)
END = date(1939, 12, 31)

INPUT = "./input-data"
EDITIONS = "./editions"
INDICES = "./indices"
BOUNDARY = "./geodata/wien-landesgrenze.geojson"

PROJECT_TITLE = "Wohin in Wien damals"

# -----------------------------------------------------------------------------

TEI_NS = "http://www.tei-c.org/ns/1.0"
T = f"{{{TEI_NS}}}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
ET.register_namespace("", TEI_NS)

ID_RE = re.compile(r"\b(person|place|work|org|event)__(\d+)\b")


def norm_id(value):
    return ID_RE.sub(r"pmb\2", value) if value else value


def normalize_ids(elem):
    """pmb-Präfixe in allen Attributen (xml:id, key, ref …) vereinheitlichen."""
    for el in elem.iter():
        for k, v in el.attrib.items():
            if "__" in v:
                el.set(k, norm_id(v))


def numeric_id(xml_id):
    m = re.search(r"(\d+)$", xml_id or "")
    return int(m.group(1)) if m else 0


# --- Geometrie ---------------------------------------------------------------

def load_boundary(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    polygons = []
    for feature in data["features"]:
        g = feature["geometry"]
        if g["type"] == "Polygon":
            polygons.append(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            polygons.extend(g["coordinates"])
    lons = [p[0] for poly in polygons for p in poly[0]]
    lats = [p[1] for poly in polygons for p in poly[0]]
    return polygons, (min(lons), min(lats), max(lons), max(lats))


def in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Vienna:
    def __init__(self, path):
        self.polygons, self.bbox = load_boundary(path)

    def contains(self, lat, lon):
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            return False
        for outer, *holes in self.polygons:
            if in_ring(lon, lat, outer) and not any(in_ring(lon, lat, h) for h in holes):
                return True
        return False


def parse_geo(text):
    """PMB-Format: '48,203 16,3691' (lat lon, Dezimalkomma)."""
    if not text:
        return None
    parts = text.split()
    if len(parts) != 2:
        return None
    try:
        lat, lon = (float(p.replace(",", ".")) for p in parts)
    except ValueError:
        return None
    return lat, lon


# --- Orte --------------------------------------------------------------------

def load_place_coords(path):
    """pmbID -> (eigene Koordinaten, Koordinaten der übergeordneten Orte)"""
    root = ET.parse(path).getroot()
    result = {}
    for place in root.iter(f"{T}place"):
        pid = place.get(XML_ID)
        if not pid:
            continue
        own, parents = [], []
        for loc in place.findall(f"{T}location"):
            geo = parse_geo(loc.findtext(f"{T}geo"))
            if geo is None:
                continue
            if loc.get("type") == "located_in_place":
                parents.append(geo)
            else:
                own.append(geo)
        result[norm_id(pid)] = (own, parents)
    return result


class PlaceResolver:
    def __init__(self, place_coords, vienna):
        self.coords = place_coords
        self.vienna = vienna
        self.cache = {}
        self.sources = Counter()

    def in_vienna(self, key, event_geo):
        if key in self.cache:
            return self.cache[key]
        own, parents = self.coords.get(key, ([], []))
        if own:
            result = self.vienna.contains(*own[0])
            self.sources["eigene Koordinaten"] += 1
        elif event_geo:
            result = self.vienna.contains(*event_geo)
            self.sources["Koordinaten im Ereignis"] += 1
        elif parents:
            result = any(self.vienna.contains(*g) for g in parents)
            self.sources["übergeordneter Ort"] += 1
        else:
            result = False
            self.sources["keine Koordinaten"] += 1
        self.cache[key] = result
        return result


# --- Ereignisse --------------------------------------------------------------

def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def event_span(event):
    start = parse_date(event.get("from-iso")) or parse_date(event.get("when-iso"))
    end = parse_date(event.get("to-iso")) or start
    if start is None:
        return None
    return start, max(start, end)


def event_in_vienna(event, resolver):
    for place in event.findall(f"{T}listPlace/{T}place"):
        pn = place.find(f"{T}placeName")
        if pn is None or not pn.get("key"):
            continue
        geo = parse_geo(place.findtext(f".//{T}geo"))
        if resolver.in_vienna(norm_id(pn.get("key")), geo):
            return True
    return False


def collect_keys(elem, tag):
    return {norm_id(e.get("key")) for e in elem.iter(f"{T}{tag}") if e.get("key")}


# --- TEI-Ausgabe -------------------------------------------------------------

def tei_document(title, source_file, description, list_tag, entries):
    tei = ET.Element(f"{T}TEI")
    header = ET.SubElement(tei, f"{T}teiHeader")
    file_desc = ET.SubElement(header, f"{T}fileDesc")
    title_stmt = ET.SubElement(file_desc, f"{T}titleStmt")
    ET.SubElement(title_stmt, f"{T}title", {"level": "s"}).text = PROJECT_TITLE
    ET.SubElement(title_stmt, f"{T}title", {"type": "main"}).text = title
    pub = ET.SubElement(file_desc, f"{T}publicationStmt")
    ET.SubElement(pub, f"{T}p").text = f"{PROJECT_TITLE}, automatisch erzeugte Daten"
    source_desc = ET.SubElement(file_desc, f"{T}sourceDesc")
    p = ET.SubElement(source_desc, f"{T}p")
    p.text = "Automatisch erzeugt aus PMB – Personen der Moderne Basis, "
    ref = ET.SubElement(p, f"{T}ref", {"target": f"https://pmb.acdh.oeaw.ac.at/media/{source_file}"})
    ref.text = source_file
    ref.tail = f". {description}"
    body = ET.SubElement(ET.SubElement(tei, f"{T}text"), f"{T}body")
    lst = ET.SubElement(body, f"{T}{list_tag}")
    lst.extend(entries)
    return ET.ElementTree(tei)


def write(tree, path):
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_index(src_name, list_tag, entry_tag, wanted, out_name, title, description):
    """Einträge aus einer PMB-Liste herausfiltern und als Register schreiben."""
    root = ET.parse(os.path.join(INPUT, src_name)).getroot()
    lst = root.find(f".//{T}body/{T}{list_tag}")
    found = []
    for entry in lst.findall(f"{T}{entry_tag}"):
        if norm_id(entry.get(XML_ID)) in wanted:
            found.append(entry)
    del root, lst
    found.sort(key=lambda e: numeric_id(e.get(XML_ID)))
    for entry in found:
        normalize_ids(entry)
    missing = wanted - {e.get(XML_ID) for e in found}
    tree = tei_document(title, src_name, description, list_tag, found)
    write(tree, os.path.join(INDICES, out_name))
    print(f"    [✓] {out_name}: {len(found)} Einträge"
          + (f", {len(missing)} nicht in der PMB-Liste gefunden" if missing else ""))
    return found


def main():
    for name in ("listevent.xml", "listplace.xml", "listperson.xml", "listbibl.xml", "listorg.xml"):
        if not os.path.exists(os.path.join(INPUT, name)):
            sys.exit(f"{INPUT}/{name} fehlt – zuerst python-scripts/fetch-data-from-pmb.py ausführen.")
    os.makedirs(EDITIONS, exist_ok=True)
    os.makedirs(INDICES, exist_ok=True)

    print("[1/3] Ereignisse filtern")
    vienna = Vienna(BOUNDARY)
    resolver = PlaceResolver(load_place_coords(os.path.join(INPUT, "listplace.xml")), vienna)

    root = ET.parse(os.path.join(INPUT, "listevent.xml")).getroot()
    events = root.findall(f".//{T}body/{T}listEvent/{T}event")
    stats = Counter()
    by_year = defaultdict(list)
    for event in events:
        span = event_span(event)
        if span is None:
            stats["ohne Datum"] += 1
            continue
        start, end = span
        if end < START or start > END:
            stats["außerhalb des Zeitraums"] += 1
            continue
        if not event_in_vienna(event, resolver):
            stats["nicht in Wien"] += 1
            continue
        stats["übernommen"] += 1
        by_year[max(start, START).year].append((start, end, numeric_id(event.get(XML_ID)), event))
    del root, events
    print(f"    Ereignisse: {dict(stats)}")
    print(f"    Ortsbestimmung über: {dict(resolver.sources)}")

    persons, places, works, orgs = set(), set(), set(), set()
    for old in glob.glob(os.path.join(EDITIONS, "listevent_*.xml")):
        os.remove(old)
    for year in sorted(by_year):
        entries = [e for *_, e in sorted(by_year[year], key=lambda x: x[:3])]
        for event in entries:
            normalize_ids(event)
            persons |= collect_keys(event, "persName")
            places |= collect_keys(event, "placeName")
            works |= collect_keys(event, "title")
            orgs |= collect_keys(event, "orgName")
        tree = tei_document(
            f"Ereignisse in Wien {year}", "listevent.xml",
            f"Auswahl: Ereignisse des Jahres {year}, deren Ort innerhalb der heutigen Wiener Stadtgrenze liegt.",
            "listEvent", entries)
        write(tree, os.path.join(EDITIONS, f"listevent_{year}.xml"))
    print(f"    [✓] {len(by_year)} Jahresdateien in {EDITIONS}/")

    print("[2/3] Werke")
    found_works = build_index(
        "listbibl.xml", "listBibl", "bibl", works, "listbibl.xml",
        "Werke", "Auswahl: Werke, auf die die Wiener Ereignisse verweisen.")
    # Urheber:innen der Werke kommen ins Personenregister
    for work in found_works:
        persons |= collect_keys(work, "author")

    print("[3/3] Personen, Orte, Institutionen")
    build_index("listperson.xml", "listPerson", "person", persons, "listperson.xml",
                "Personen", "Auswahl: Personen, die an den Wiener Ereignissen beteiligt sind, "
                "sowie Urheber:innen der aufgeführten Werke.")
    build_index("listplace.xml", "listPlace", "place", places, "listplace.xml",
                "Orte", "Auswahl: Orte der Wiener Ereignisse.")
    build_index("listorg.xml", "listOrg", "org", orgs, "listorg.xml",
                "Institutionen", "Auswahl: Institutionen, die die Wiener Ereignisse veranstaltet haben.")


if __name__ == "__main__":
    main()
