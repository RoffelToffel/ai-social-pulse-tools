#!/usr/bin/env python3
"""Versand-Historie über die Brevo-API (getestet 01.11.2026).

  python3 -I tools/brevo_history.py window [--now <unix>]
      JSON mit dem letzten Briefing eines FRÜHEREN Tages, Fensterstart (UTC),
      Fensterlänge und ob das Fenster erweitert wurde. Briefings vom selben Tag
      (z.B. manuelle Testläufe) werden ignoriert, aber informativ aufgelistet.
  python3 -I tools/brevo_history.py content <uuid> --out out/prev_briefing.html
      Speichert den HTML-Body eines versendeten Briefings (für den Abgleich).

Regel: Fensterstart = früherer Zeitpunkt aus (JETZT − 24 h) und der Versandzeit des
letzten Briefings eines früheren Tages, aber nie weiter zurück als JETZT − 72 h.
Env: BREVO_API_KEY (Pflicht), BRIEFING_TO (Fallback: config/defaults.json).
Der API-Key wird nie ausgegeben oder gespeichert.
"""
import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SUBJ = re.compile(r"^AI Social Pulse – Dein KI-Briefing für den (\d{2})\.(\d{2})\.(\d{4})")


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
    st, d = api("/smtp/emails?" + urllib.parse.urlencode({"email": to, "limit": 50, "sort": "desc"}), key)
    briefings = []
    if st == 200:
        for e in d.get("transactionalEmails", []):
            m = SUBJ.match(e.get("subject") or "")
            if not m:
                continue
            sent = dt.datetime.fromisoformat(e["date"]).astimezone(UTC)
            briefings.append({"subject_date": dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
                              "sent_utc": sent, "uuid": e.get("uuid"), "subject": e.get("subject")})
    else:
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
        "window_hours": round((now - start).total_seconds() / 3600, 2),
        "extended": (now - start) > dt.timedelta(hours=26),  # nur echte Lücken (z.B. ausgefallener Lauf)
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


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("window")
    w.add_argument("--now", type=int)
    c = sub.add_parser("content")
    c.add_argument("uuid")
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("BREVO_API_KEY fehlt")
    to = os.environ.get("BRIEFING_TO", "").strip() or defaults()["fallback"]["BRIEFING_TO"]
    if a.cmd == "window":
        cmd_window(a, key, to)
    else:
        cmd_content(a, key)


if __name__ == "__main__":
    main()
