#!/usr/bin/env python3
"""Original-Links der Techmeme-Einträge (getestet 01.11.2026).

  python3 -I tools/techmeme_links.py

Gibt je Feed-Eintrag pubDate, Titel und die verlinkte Erstmeldung aus. Datum in der
Original-URL prüfen: Techmeme spült am Wochenende oft Tage alte Meldungen hoch.
(ElementTree for the XML, HTMLParser for the embedded HTML)."""
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

CA = "/root/.ccr/ca-bundle.crt"
UA = "AISocialPulseBriefingBot/1.0 (daily AI digest)"


class A(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            h = dict(attrs).get("href")
            if h and "techmeme.com" not in h:
                self.links.append(h)


req = urllib.request.Request("https://www.techmeme.com/feed.xml", headers={"User-Agent": UA})
raw = urllib.request.urlopen(req, context=ssl.create_default_context(cafile=CA), timeout=30).read()
root = ET.fromstring(raw)
for it in root.iter("item"):
    t = "".join(it.find("title").itertext())
    d = "".join(it.find("description").itertext()) if it.find("description") is not None else ""
    p = A()
    p.feed(d)
    print(it.find("pubDate").text, "|", t[:90])
    for l in p.links[:2]:
        print("    ", l)
