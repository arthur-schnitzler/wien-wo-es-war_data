# Wohin in Wien damals (Data)
Data repository containing events in Vienna (Austria) between 1860 and 1939 as XML-files for every year

Dieses Repositorium versammelt Einträge aus verschiedenen Aufführungsdatenbanken und online-Quellen und verbindet sie zeitlich und lokal. Es handelt sich nur um kulturelle Ereignisse, die in Wien stattgefunden haben. Während Aufführungen in den zentralen Häusern (Oper, Burgtheater) vollständig erfasst sind, ist das bei anderen Häusern nicht der Fall. Die Website selbst befindet sich in Vorbereitung. Das dazugehörige Repositorium findet sich unter https://github.com/arthur-schnitzler/wohin-in-wien-damals_static/

Aufgenommen sind Einträge aus:

## Burgtheater, Kulturerbe digital
Das Burgtheater hat 2026 ein historisches Verzeichnis aller Veranstaltungen in ihrem Haus und den dazugehörigen Spielstätten veröffentlicht. Daraus wurden jene Ereignisse entnommen, die den Zeitraum 1850–1945 erfassen, sowie die gespielten Theaterstücke. Die Beziehungen zwischen Schauspielerinnen und Schauspielern und Ereignissen wurden nicht übernommen. https://kulturerbe.burgtheater.at

## Spielplan Oper 1850–1945
Die Sammlung umfasst alle Aufführungen bis 1945, die im »Spielplan der Wiener Oper 1869 bis 1955« https://www.mdw.ac.at/imi/operapolitics/spielplan-wiener-oper/web/ aufgenommen sind. Erstellt wurde sie von Christian Glanz, Thomas Hübl, Carolin Bahr u.a. 
knapp 35.000 Ereignisse, 500 Werke, 600 Personen, ergänzt November 2026

## Arthur Schnitzler – Kulturveranstaltungen. 
Theateraufführungen, Konzerte, Premieren, Kinoabende und andere Veranstaltungen – mehr als zweimal jede Woche war Arthur Schnitzler unterwegs und nahm am kulturellen Leben teil. Die Website https://schnitzler-kultur.acdh.oeaw.ac.at versammelt erstmals über 6.200 Ereignisse, die er zwischen 1876 und 1931 besuchte und macht sie zugänglich. Das umfasst alle Veranstaltungen, bei denen er selbst tätig wurde, wie seine seltenen öffentlichen Lesungen. Es umfasst auch die Lesungen aus seinen (zumeist noch unveröffentlichten) Werken im privaten Kreis. Somit sind erstmals auch alle Theaterproben, Besuche im Kaiserpanorama, Bälle und Soiréen schnell auffindbar.

## Arthur Schnitzler: Briefwechsel mit Autorinnen und Autoren
Das aktivste Projekt der PMB, das die Kuratierung der meisten Datensätze übernommen hat, https://schnitzler-briefe.acdh.oeaw.ac.at/. Während viele der Ereignisse auch in Schnitzler-Kultur vorkommen (weil Schnitzler teilnahm), legt das Projekt auch Ereignisse an, an denen Schnitzler nicht teilgenommen hat, die aber in seiner Korrespondenz Erwähnung finden.


# In Vorbereitung:
* Karl Kraus als Vorleser

## Mögliche weitere Datengeber:

* Konzerthaus: https://konzerthaus.at/de/archiv-suche
* Musikverein: https://musikverein.at/archiv/konzertarchiv/
* Singverein der Gesellschaft der Musikfreunde, https://www.singverein.at/archiv
* Volksoper?
* Wiener Philharmoniker, Konzertarchiv: https://www.wienerphilharmoniker.at/de/konzert-archiv
  
Wir freuen uns über weitere Datenbestände und bitten um Kontaktaufnahme!


# Technisches

## Daten

* `editions/listevent_YYYY.xml` – ein TEI-Dokument pro Jahr (1860–1939) mit allen Ereignissen dieses Jahres, chronologisch sortiert
* `indices/listperson.xml` – Personen, die an den Ereignissen beteiligt sind (mitwirkend, teilnehmend), sowie die Urheber:innen der aufgeführten Werke
* `indices/listplace.xml` – Orte der Ereignisse
* `indices/listbibl.xml` – Werke, auf die die Ereignisse verweisen (aufgeführt, gelesen, rezensiert …)
* `indices/listorg.xml` – Institutionen, die die Ereignisse veranstaltet haben

Alle Kennungen sind wie in den anderen Projekten zu `pmbXXXX` vereinheitlicht (PMB: `event__XXXX`, `person__XXXX`, `place__XXXX`, `work__XXXX`, `org__XXXX`). Die Verweise in den Ereignissen (`@key`) zeigen auf die `@xml:id` der Register.

## Auswahl

Aus `https://pmb.acdh.oeaw.ac.at/media/listevent.xml` werden die Ereignisse übernommen, die

* **zeitlich** in den Zeitraum 1.1.1860–31.12.1939 fallen (`@when-iso` bzw. `@from-iso`/`@to-iso`; Ereignisse ohne Datum entfallen) und
* **räumlich** an mindestens einem Ort innerhalb der heutigen Wiener Stadtgrenze stattgefunden haben.

Für die Ortsbestimmung werden die Koordinaten des Ortes aus der PMB (`listplace.xml`) gegen das Polygon der Wiener Landesgrenze (`geodata/wien-landesgrenze.geojson`, Stadt Wien – data.wien.gv.at, CC BY 4.0) geprüft. Hat ein Ort keine eigenen Koordinaten, werden die des übergeordneten Ortes (`located_in_place`, meist „Wien") verwendet. Da die heutige Stadtgrenze zugrunde liegt, zählen auch Orte in den erst 1892, 1904 bzw. 1938 eingemeindeten Gebieten zu Wien.

Zeitraum und Pfade lassen sich am Anfang von `python-scripts/build-data.py` anpassen.

## Aktualisieren

Lokal (nur Python 3.9+, keine weiteren Abhängigkeiten):

```bash
python3 python-scripts/fetch-data-from-pmb.py   # lädt die PMB-Exporte nach input-data/ (~200 MB, nicht versioniert)
python3 python-scripts/build-data.py            # erzeugt editions/ und indices/
```

Auf GitHub erledigt das der Workflow `Update Data from PMB` (`.github/workflows/update-data.yml`, manuell über *Actions → Run workflow*). Er committet `editions/` und `indices/`, sofern sich etwas geändert hat.
