#!/usr/bin/env python3
"""Live-Prüfung eines X/Twitter-Posts über den fxtwitter-Spiegel (getestet 01.11.2026).

  python3 -I tools/x_post.py https://x.com/<user>/status/<id>
  python3 -I tools/x_post.py <user>/status/<id>

Ausgabe (JSON): created_utc, Autor, Originaltext, Likes/Reposts/Antworten.
So geprüfte Posts gelten als live verifiziert; im Briefing als "über fxtwitter geprüft"
kennzeichnen. Zitate realer Personen trotzdem sparsam und mit Link zum Original.
"""
import datetime as dt
import json
import re
import ssl
import sys
import urllib.error
import urllib.request

CA = "/root/.ccr/ca-bundle.crt"
UA = "AISocialPulseBriefingBot/1.0 (daily AI digest)"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arg = sys.argv[1].strip()
    m = (re.search(r"(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)/status/(\d+)", arg)
         or re.match(r"([A-Za-z0-9_]+)/status/(\d+)", arg))
    if not m:
        sys.exit("Unbekanntes Format – erwartet x.com/<user>/status/<id>")
    user, sid = m.group(1), m.group(2)
    api = f"https://api.fxtwitter.com/{user}/status/{sid}"
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(cafile=CA), timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(json.dumps({"ok": False, "http": e.code, "api": api}))
        sys.exit(1)
    t = d.get("tweet") or {}
    ts = t.get("created_timestamp")
    author = t.get("author") or {}
    print(json.dumps({
        "ok": d.get("code") == 200 and bool(t),
        "verified_via": "fxtwitter",
        "original_url": f"https://x.com/{user}/status/{sid}",
        "created_utc": dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat() if ts else None,
        "created_unix": ts,
        "author_name": author.get("name"),
        "author_handle": author.get("screen_name"),
        "text": t.get("text"),
        "likes": t.get("likes"), "reposts": t.get("retweets"), "replies": t.get("replies"),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
