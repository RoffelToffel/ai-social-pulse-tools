#!/usr/bin/env python3
"""Versand-Historie über die Brevo-API (getestet 01.11. und 02.11.2026).

  python3 -I tools/brevo_history.py window [--now <unix>]
      JSON mit dem letzten Briefing eines FRÜHEREN Tages, Fensterstart und -ende (UTC),
      Fensterlänge und ob das Fenster erweitert wurde. Briefings vom selben Tag
      (z.B. manuelle Testläufe) werden ignoriert, aber informativ aufgelistet.
      now_utc, window_start_utc und extended direkt ins Briefing-JSON übernehmen
      (now_utc, window_start_utc, window_extended).
  python3 -I tools/brevo_history.py content <uuid> --out out/prev_briefing.html
      Speichert den HTML-Body eines versendeten Briefings (für den Abgleich).
  python3 -I tools/brevo_history.py recent [--days 7] --out-dir out/hist
      Lädt das jeweils letzte Briefing jedes früheren Tages der letzten N Tage und
      speichert HTML und Text (<JJJJ-MM-TT>.html/.txt) für den Abgleich; gibt einen Index aus.

Regel: Fensterstart = früherer Zeitpunkt aus (JETZT − 24 h) und der Versandzeit des
letzten Briefings eines früheren Tages, aber nie weiter zurück als JETZT − 72 h.
Fensterende = JETZT (Redaktionsschluss). Erweitert ist das Fenster, wenn es mehr als
24 h + 6 min umfasst (dieselbe Regel wie in render_briefing.py).
Env: BREVO_API_KEY (Pflicht), BRIEFING_TO (Fallback: config/defaults.json).
Der API-Key wird nie ausgegeben oder gespeichert.
"""
import argparse
import datetime as dt
import html as htmllib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SUBJ = re.compile(r"^AI Social Pulse – Dein KI-Briefing für den (\d{2})\.(\d{2})\.(\d{4})")
EXTENDED_AFTER = dt.timedelta(hours=24, minutes=6)
BLOCK = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "td", "br", "table"}


class _Text(HTMLParser):
    """HTML -> Text mit Zeilenumbrüchen an Blockelementen (ohne Regex-Tag-Stripping)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(s):
    p = _Text()
    p.feed(s or "")
    lines = (" ".join(htmllib.unescape(l).split()) for l in "".join(p.parts).splitlines())
    return "\n".join(l for l in lines if l)


def list_briefings(key, to):
    st, d = api("/smtp/emails?" + urllib.parse.urlencode({"email": to, "limit": 50, "sort": "desc"}), key)
    out = []
    if st == 200:
        for e in d.get("transactionalEmails", []):
            m = SUBJ.match(e.get("subject") or "")
            if m:
                out.append({"subject_date": dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
                            "sent_utc": dt.datetime.fromisoformat(e["date"]).astimezone(UTC),
                            "uuid": e.get("uuid"), "subject": e.get("subject")})
    return st, d, out


def defaults():
    with open(os.path.join(ROOT, "config", "defaults.json"), encoding="utf-8") as fh:
        return json.load(fh)


def api(path, key):
    req = urllib.request.Request("https://api.brevo.com/v3" + path, headers={
        "api-key": key, "Accept": "application/json", "User-Agent": "AISocialPulseBriefing/1.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}


def cmd_window(a, key, to):
    now = dt.datetime.fromtimestamp(a.now or time.time(), UTC)
    today = now.astimezone(BERLIN).date()
    out = {"now_utc": now.isoformat(), "today_berlin": today.isoformat(), "source": "brevo"}
    st, d, briefings = list_briefings(key, to)
    if st != 200:
        out.update(source="fallback-24h", error=f"HTTP {st}: {d.get('error', '')}")
    prev = max((b for b in briefings if b["subject_date"] < today), key=lambda b: b["sent_utc"], default=None)
    same_day = [b for b in briefings if b["subject_date"] == today]
    start = now - dt.timedelta(hours=24)
    if prev and prev["sent_utc"] < start:
        start = max(prev["sent_utc"], now - dt.timedelta(hours=72))
    ser = lambda b: {"sent_utc": b["sent_utc"].isoformat(), "subject": b["subject"], "uuid": b["uuid"]}
    out.update({
        "previous_briefing": ser(prev) if prev else None,
        "same_day_briefings_ignored": [ser(b) for b in same_day],
        "window_start_utc": start.isoformat(),
        "window_start_unix": int(start.timestamp()),
        "window_end_utc": now.isoformat(),  # Fensterende = JETZT (Redaktionsschluss)
        "window_hours": round((now - start).total_seconds() / 3600, 2),
        "extended": (now - start) > EXTENDED_AFTER,  # -> window_extended im Briefing-JSON
    })
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_content(a, key):
    st, d = api("/smtp/emails/" + urllib.parse.quote(a.uuid, safe=""), key)
    if st != 200:
        sys.exit(f"HTTP {st}: {d.get('error', '')}")
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(d.get("body") or "")
    print(json.dumps({"subject": d.get("subject"), "date": d.get("date"), "body_chars": len(d.get("body") or ""),
                      "events": [e.get("name") for e in d.get("events", [])], "saved": a.out},
                     ensure_ascii=False, indent=1))


def cmd_recent(a, key, to):
    now = dt.datetime.now(UTC)
    today = now.astimezone(BERLIN).date()
    st, d, briefings = list_briefings(key, to)
    if st != 200:
        sys.exit(f"HTTP {st}: {d.get('error', '')}")
    latest = {}
    for b in briefings:  # pro Tag das zuletzt versendete Briefing; heute (Testläufe) ignorieren
        if today - dt.timedelta(days=a.days) <= b["subject_date"] < today:
            if b["subject_date"] not in latest or b["sent_utc"] > latest[b["subject_date"]]["sent_utc"]:
                latest[b["subject_date"]] = b
    os.makedirs(a.out_dir, exist_ok=True)
    index = []
    for day in sorted(latest, reverse=True):
        b = latest[day]
        st2, d2 = api("/smtp/emails/" + urllib.parse.quote(b["uuid"], safe=""), key)
        if st2 != 200:
            index.append({"date": day.isoformat(), "uuid": b["uuid"], "error": f"HTTP {st2}"})
            continue
        body = d2.get("body") or ""
        base = os.path.join(a.out_dir, day.isoformat())
        open(base + ".html", "w", encoding="utf-8").write(body)
        text = html_to_text(body)
        open(base + ".txt", "w", encoding="utf-8").write(text)
        index.append({"date": day.isoformat(), "sent_utc": b["sent_utc"].isoformat(), "subject": b["subject"],
                      "uuid": b["uuid"], "text": base + ".txt", "chars": len(text)})
    print(json.dumps(index, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("window")
    w.add_argument("--now", type=int)
    c = sub.add_parser("content")
    c.add_argument("uuid")
    c.add_argument("--out", required=True)
    r = sub.add_parser("recent")
    r.add_argument("--days", type=int, default=7)
    r.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("BREVO_API_KEY fehlt")
    to = os.environ.get("BRIEFING_TO", "").strip() or defaults()["fallback"]["BRIEFING_TO"]
    if a.cmd == "window":
        cmd_window(a, key, to)
    elif a.cmd == "recent":
        cmd_recent(a, key, to)
    else:
        cmd_content(a, key)


if __name__ == "__main__":
    main()
