#!/usr/bin/env python3
"""RSS/Atom-Abruf und -Parser für AI Social Pulse (getestet 01.11.2026).

- Echtes XML-Parsing via ElementTree (CDATA-sicher, kein Regex-Tag-Stripping:
  `<[^>]+>` verschluckt CDATA-Titel von Bloomberg, Guardian, TechCrunch still).
- RSS 2.0 (<item>/<pubDate>, dc:date), RSS 1.0/RDF und Atom (<entry>/<published>/<updated>).
- Normalisiert alle Zeitstempel nach UTC und filtert auf das Zeitfenster.

Aufruf (immer mit -I, weil heruntergeladene Daten verarbeitet werden):
  python3 -I tools/feeds.py --now <unix> --since <unix> --out out/news.json \
      --file config/feeds_international.txt --file config/feeds_dach.txt
  python3 -I tools/feeds.py --now <unix> --hours 24 --out out/x.json URL [URL ...]
Optionen:
  --since <unix>  Fensterstart (hat Vorrang vor --hours)
  --hours <h>     Fensterlänge, wenn --since fehlt (Standard 24)
  --all           auch Einträge außerhalb des Fensters behalten
"""
import argparse
import datetime as dt
import email.utils
import html
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = "AISocialPulseBriefingBot/1.0 (+daily AI news digest; python-urllib)"
CA = "/root/.ccr/ca-bundle.crt"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss1": "http://purl.org/rss/1.0/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s):
    if not s:
        return ""
    p = _TextOnly()
    try:
        p.feed(s)
        p.close()
        out = "".join(p.parts)
    except Exception:
        out = s
    return " ".join(html.unescape(out).split())


def parse_date(s):
    """Aware UTC datetime oder None."""
    if not s:
        return None
    s = s.strip()
    try:  # RFC 822/2822 (RSS pubDate)
        d = email.utils.parsedate_to_datetime(s)
        if d is not None:
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:  # ISO 8601 (Atom, dc:date)
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _txt(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def fetch(url, retries=2, timeout=30):
    """(status, bytes). HTTP 429 = Rate-Limit (z.B. Reddit) -> 25 s warten, erneut."""
    ctx = ssl.create_default_context(cafile=CA)
    last = ("ERR", b"")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = (e.code, b"")
            if e.code == 429 and attempt < retries:
                time.sleep(25)
                continue
            return e.code, b""
        except Exception as e:
            last = (f"ERR {type(e).__name__}: {e}", b"")
            if attempt < retries:
                time.sleep(3)
    return last


def parse_feed(raw, source):
    items = []
    root = ET.fromstring(raw)
    tag = root.tag.lower()
    if tag.endswith("}feed") or tag == "feed":  # Atom
        for e in root.findall("atom:entry", NS):
            link = ""
            for l in e.findall("atom:link", NS):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            if not link:
                l = e.find("atom:link", NS)
                link = l.get("href", "") if l is not None else ""
            pub = _txt(e.find("atom:published", NS))
            upd = _txt(e.find("atom:updated", NS))
            summ = _txt(e.find("atom:summary", NS)) or _txt(e.find("atom:content", NS))
            items.append({
                "source": source, "title": html_to_text(_txt(e.find("atom:title", NS))), "link": link,
                "date_raw": pub or upd, "date_field": "published" if pub else "updated",
                "summary": html_to_text(summ)[:400],
            })
        return items
    if tag.endswith("}rdf"):  # RSS 1.0
        for e in root.findall("rss1:item", NS):
            items.append({
                "source": source, "title": html_to_text(_txt(e.find("rss1:title", NS))),
                "link": _txt(e.find("rss1:link", NS)), "date_raw": _txt(e.find("dc:date", NS)),
                "date_field": "dc:date", "summary": html_to_text(_txt(e.find("rss1:description", NS)))[:400],
            })
        return items
    for e in root.iter("item"):  # RSS 2.0
        pub, field = _txt(e.find("pubDate")), "pubDate"
        if not pub:
            pub, field = _txt(e.find("dc:date", NS)), "dc:date"
        src_el = e.find("source")
        items.append({
            "source": source, "title": html_to_text(_txt(e.find("title"))),
            "link": _txt(e.find("link")) or _txt(e.find("guid")),
            "date_raw": pub, "date_field": field,
            "publisher": _txt(src_el) if src_el is not None else "",  # Google News: Verlag
            "comments": _txt(e.find("comments")),
            "summary": html_to_text(_txt(e.find("description")))[:400],
        })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", type=int, required=True, help="JETZT als UNIX-UTC")
    ap.add_argument("--since", type=int, help="Fensterstart als UNIX-UTC")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--file", action="append", default=[], help="Datei mit einer Feed-URL pro Zeile")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("urls", nargs="*")
    a = ap.parse_args()

    urls = list(a.urls)
    for f in a.file:
        with open(f) as fh:
            urls += [l.strip() for l in fh if l.strip() and not l.lstrip().startswith("#")]

    now = dt.datetime.fromtimestamp(a.now, dt.timezone.utc)
    cutoff = (dt.datetime.fromtimestamp(a.since, dt.timezone.utc) if a.since
              else now - dt.timedelta(hours=a.hours))
    out, report = [], []
    for url in urls:
        status, raw = fetch(url)
        if status != 200 or not raw:
            report.append((url, status, 0, 0))
            print(f"[FAIL] {status} {url}", file=sys.stderr)
            continue
        try:
            items = parse_feed(raw, url)
        except ET.ParseError as e:
            report.append((url, f"XML-ParseError {e}", 0, 0))
            print(f"[XMLERR] {url}: {e}", file=sys.stderr)
            continue
        kept = empty = 0
        for it in items:
            empty += not it["title"]
            d = parse_date(it.get("date_raw"))
            it["pub_utc"] = d.isoformat() if d else None
            it["age_h"] = round((now - d).total_seconds() / 3600, 2) if d else None
            it["in_window"] = bool(d and cutoff <= d <= now + dt.timedelta(minutes=5))
            if it["in_window"] or a.all:
                out.append(it)
                kept += it["in_window"]
        report.append((url, status, len(items), kept))
        warn = f" (WARN {empty} leere Titel)" if empty else ""
        print(f"[OK] {url}: {len(items)} items, {kept} im Fenster{warn}", file=sys.stderr)
        time.sleep(0.5)

    out.sort(key=lambda x: x.get("pub_utc") or "", reverse=True)
    with open(a.out, "w") as fh:
        json.dump({"now_utc": now.isoformat(), "cutoff_utc": cutoff.isoformat(),
                   "report": report, "items": out}, fh, ensure_ascii=False, indent=1)
    print(f"{len(out)} Einträge -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
