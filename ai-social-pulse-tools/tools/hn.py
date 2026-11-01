#!/usr/bin/env python3
"""Hacker-News-Helfer über die offiziellen APIs (getestet 01.11.2026).

  python3 -I tools/hn.py search <since_unix> <min_points> begriff1 begriff2 ...
      Stories seit <since_unix> mit mehr als <min_points> Punkten (Algolia).
      Einzelbegriffe abfragen – OR-Syntax liefert bei Algolia keine Treffer.
      Ausgabe: ID | Punkte | Kommentare | Punkte/h | Zeit (UTC) | Titel | URL
  python3 -I tools/hn.py item <id> [max_kommentare]
      Exakter Zeitstempel (Firebase, Feld "time") + Kommentarbaum (Algolia).
"""
import datetime as dt
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

CA = "/root/.ccr/ca-bundle.crt"
UA = "AISocialPulseBriefingBot/1.0 (daily AI digest)"
CTX = ssl.create_default_context(cafile=CA)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return json.loads(r.read())


class _T(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.p = []

    def handle_data(self, d):
        self.p.append(d)

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.p.append(" ")


def txt(h):
    t = _T()
    t.feed(h or "")
    return " ".join("".join(t.p).split())


def fmt(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def search(since, minp, terms):
    seen = {}
    for term in terms:
        q = urllib.parse.urlencode({
            "query": term, "tags": "story",
            "numericFilters": f"created_at_i>{since},points>{minp}", "hitsPerPage": 50,
        })
        try:
            d = get(f"https://hn.algolia.com/api/v1/search_by_date?{q}")
        except Exception as e:
            print(f"# {term!r}: FEHLER {e}", file=sys.stderr)
            continue
        print(f"# {term!r}: {d.get('nbHits')} Treffer", file=sys.stderr)
        for h in d.get("hits", []):
            seen.setdefault(h["objectID"], h)
        time.sleep(0.3)
    now = time.time()
    for h in sorted(seen.values(), key=lambda h: -(h.get("points") or 0)):
        hours = max((now - h["created_at_i"]) / 3600, 0.5)
        rate = (h.get("points") or 0) / hours
        print(f"{h['objectID']:>9} | {h.get('points'):4}p | {h.get('num_comments') or 0:4}c | "
              f"{rate:5.1f}p/h | {fmt(h['created_at_i'])} | {h.get('title')} | {h.get('url') or ''}")


def item(iid, maxc=40):
    fb = get(f"https://hacker-news.firebaseio.com/v0/item/{iid}.json")
    print(f"FIREBASE id={iid} time={fb.get('time')} ({fmt(fb.get('time'))}) score={fb.get('score')} "
          f"descendants={fb.get('descendants')} title={fb.get('title')!r} url={fb.get('url')}")
    al = get(f"https://hn.algolia.com/api/v1/items/{iid}")
    out = []

    def walk(node, depth):
        for c in node.get("children", []) or []:
            if c.get("text"):
                out.append((depth, c.get("author"), c.get("created_at"), txt(c.get("text"))))
            walk(c, depth + 1)
    walk(al, 0)
    print(f"Kommentare gesamt (Algolia)={len(out)}, Top-Level={sum(1 for o in out if o[0] == 0)}")
    for depth, a, t, body in out[:maxc]:
        print(f"{'  ' * depth}- [{a} {t}] {body[:420]}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[1] == "search":
        search(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:])
    elif sys.argv[1] == "item":
        item(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 40)
    else:
        sys.exit(__doc__)
