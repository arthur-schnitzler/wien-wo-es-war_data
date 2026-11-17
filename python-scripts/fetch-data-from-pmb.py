#!/usr/bin/env python3
"""
Lädt die TEI-Exporte der PMB (https://pmb.acdh.oeaw.ac.at/media/) nach
./input-data/ herunter. Die Dateien sind groß (zusammen rund 200 MB) und
werden nicht versioniert; daraus erzeugt build-data.py die Ereignisse
(editions/) und Register (indices/).
"""

import os
import shutil
import sys
import time
import urllib.request

BASE_URL = "https://pmb.acdh.oeaw.ac.at/media/"
FILES = [
    "listevent.xml",
    "listplace.xml",
    "listperson.xml",
    "listbibl.xml",
    "listorg.xml",
]
OUTPUT_FOLDER = "./input-data"
RETRIES = 3


def download(url, target):
    tmp = target + ".part"
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wohin-in-wien-damals"})
            with urllib.request.urlopen(req, timeout=300) as response, open(tmp, "wb") as f:
                shutil.copyfileobj(response, f, length=1024 * 1024)
            os.replace(tmp, target)
            return
        except Exception as e:  # noqa: BLE001
            print(f"    [!] Versuch {attempt}/{RETRIES} fehlgeschlagen: {e}")
            if attempt == RETRIES:
                raise
            time.sleep(10 * attempt)


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    for i, name in enumerate(FILES, 1):
        url = BASE_URL + name
        target = os.path.join(OUTPUT_FOLDER, name)
        print(f"[{i}/{len(FILES)}] {url}")
        download(url, target)
        size = os.path.getsize(target) / 1024 / 1024
        print(f"    [✓] gespeichert unter {target} ({size:.1f} MB)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Download fehlgeschlagen: {e}")
