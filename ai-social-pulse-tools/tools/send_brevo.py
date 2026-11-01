#!/usr/bin/env python3
"""Versand über die Brevo-HTTPS-API (nie SMTP) inkl. Zustellprüfung (getestet 01.11.2026).

  python3 -I tools/send_brevo.py --out out/ [--dry-run]

Liest out/briefing.html, out/briefing.txt und out/meta.json (von render_briefing.py) und
sendet NUR, wenn meta.json "qa_passed": true enthält und kein "preview_only" gesetzt ist.
Absender/Empfänger: BRIEFING_FROM, BRIEFING_FROM_NAME, BRIEFING_TO (Fallbacks in
config/defaults.json; Fallback-Nutzung im Abschlussbericht melden).
API-Key ausschließlich aus BREVO_API_KEY (muss mit "xkeysib-" beginnen; ein "xsmtpsib-"-Key
ist ein SMTP-Key und liefert 401 "Key not found"). Der Key wird nie ausgegeben oder gespeichert.
HTTP 201 = akzeptiert. Transiente Fehler (401 mit IP-Bezug, 429, 5xx): bis zu 3 Wiederholungen
mit ~15 s Abstand, Inhalt unverändert. Danach "delivered"-Event über die Events-API prüfen
(kam am 01.11.2026 nach ~60 s).
"""
import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    defaults = json.load(open(os.path.join(ROOT, "config", "defaults.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(a.out, "meta.json"), encoding="utf-8"))
    html_body = open(os.path.join(a.out, "briefing.html"), encoding="utf-8").read()
    text_body = open(os.path.join(a.out, "briefing.txt"), encoding="utf-8").read()

    if not meta.get("qa_passed") or meta.get("preview_only"):
        sys.exit("ABBRUCH: QA nicht bestanden oder Vorschau-Rendering – kein Versand. "
                 f"Fehler: {meta.get('errors')}")

    cfg, used_fallback = {}, []
    for k, fb in defaults["fallback"].items():
        v = os.environ.get(k, "").strip()
        if not v:
            v = fb
            used_fallback.append(k)
        cfg[k] = v
    subject = meta["subject"]
    brand = defaults["brand"]
    if cfg["BRIEFING_FROM_NAME"] != brand or not subject.startswith(brand):
        sys.exit(f"ABBRUCH: Absendername ({cfg['BRIEFING_FROM_NAME']!r}) und Betreff tragen nicht dieselbe Marke ({brand!r}).")

    print("== Versandparameter ==")
    print(f"Absender  : {cfg['BRIEFING_FROM_NAME']} <{cfg['BRIEFING_FROM']}>")
    print(f"Empfänger : {cfg['BRIEFING_TO']}")
    print(f"Betreff   : {subject}")
    print(f"Fallbacks : {', '.join(used_fallback) if used_fallback else 'keine (alle Variablen gesetzt)'}")
    print(f"HTML {len(html_body)} Zeichen, Text {len(text_body)} Zeichen")

    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("ABBRUCH: BREVO_API_KEY ist nicht gesetzt.")
    if not key.startswith("xkeysib-"):
        sys.exit("ABBRUCH: BREVO_API_KEY beginnt nicht mit 'xkeysib-' (evtl. SMTP-Key 'xsmtpsib-').")
    if a.dry_run:
        print("DRY-RUN: Key-Format ok, nichts gesendet.")
        return

    payload = json.dumps({
        "sender": {"email": cfg["BRIEFING_FROM"], "name": cfg["BRIEFING_FROM_NAME"]},
        "to": [{"email": cfg["BRIEFING_TO"]}],
        "subject": subject, "htmlContent": html_body, "textContent": text_body,
    }).encode("utf-8")

    def call(method, url, data=None):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "api-key": key, "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "AISocialPulseBriefing/1.0"})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    status, body, message_id = None, "", None
    for attempt in range(1, 5):
        status, body = call("POST", "https://api.brevo.com/v3/smtp/email", payload)
        print(f"Versuch {attempt}: HTTP {status} {body[:300]}")
        if status == 201:
            message_id = json.loads(body).get("messageId")
            break
        transient = status == 429 or (status is not None and status >= 500) or (
            status == 401 and ("ip" in body.lower() or "unrecognised" in body.lower()))
        if not transient or attempt == 4:
            print(f"DAUERHAFTER FEHLER: HTTP {status}: {body}")
            sys.exit(1)
        time.sleep(15)

    print(f"== Akzeptiert: HTTP {status}, Message-Id {message_id}")
    result = {"status": status, "messageId": message_id, "subject": subject,
              "to": cfg["BRIEFING_TO"], "fallbacks": used_fallback, "events": [], "delivered": False}
    q = urllib.parse.quote(message_id, safe="")
    for i in range(12):
        time.sleep(10 if i else 6)
        st, ev = call("GET", f"https://api.brevo.com/v3/smtp/statistics/events?limit=20&messageId={q}")
        try:
            events = json.loads(ev).get("events", []) if st == 200 else []
        except json.JSONDecodeError:
            events = []
        names = [e.get("event") for e in events]
        print(f"Event-Check {i + 1}: HTTP {st}, Events {names}")
        result["events"] = events
        if "delivered" in names:
            result["delivered"] = True
            break
        if any(n in ("hardBounces", "softBounces", "blocked", "invalid", "error") for n in names):
            break
    json.dump(result, open(os.path.join(a.out, "send_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("== Zustellung:", "DELIVERED" if result["delivered"] else "noch kein 'delivered'-Event")
    for e in result["events"]:
        print("   ", {k: e.get(k) for k in ("event", "date", "email", "reason")})


if __name__ == "__main__":
    main()
