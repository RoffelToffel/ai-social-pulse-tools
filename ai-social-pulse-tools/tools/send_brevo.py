#!/usr/bin/env python3
"""Versand über die Brevo-HTTPS-API (nie SMTP) inkl. Zustellprüfung (getestet 01.11. und 02.11.2026).

  python3 -I tools/send_brevo.py --out out/ [--dry-run] [--wait 8]
  python3 -I tools/send_brevo.py --check "<Message-Id>" [--wait 25] [--out out/]

Versand: liest out/briefing.html, out/briefing.txt und out/meta.json (von render_briefing.py)
und sendet NUR, wenn meta.json "qa_passed": true enthält und kein "preview_only" gesetzt ist.
Absender/Empfänger: BRIEFING_FROM, BRIEFING_FROM_NAME, BRIEFING_TO (Fallbacks in
config/defaults.json; Fallback-Nutzung im Abschlussbericht melden).
API-Key ausschließlich aus BREVO_API_KEY (muss mit "xkeysib-" beginnen; ein "xsmtpsib-"-Key
ist ein SMTP-Key und liefert 401 "Key not found"). Der Key wird nie ausgegeben oder gespeichert.
HTTP 201 = akzeptiert. Transiente Fehler (401 mit IP-Bezug, 429, 5xx): bis zu 3 Wiederholungen
mit ~15 s Abstand, Inhalt unverändert.

Zustellprüfung: Events-API bis zu --wait Minuten (Standard 8; die ersten 2 Minuten alle 10 s,
danach jede Minute). Am 01.11.2026 kam "delivered" nach ~60 s, am 02.11.2026 erst nach ~22 min
(zugestellt war die Mail nach 3 s – die Events-API hing hinterher). Nach HTTP 201 NIE erneut
senden; bleibt das Event aus, später mit --check weiterprüfen (für lange Wartezeiten im
Hintergrund starten). Ergebnis in out/send_result.json bzw. out/check_result.json.
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
API = "https://api.brevo.com/v3"
FINAL_BAD = ("hardBounces", "softBounces", "blocked", "invalid", "error")


def make_call(key):
    def call(method, path, data=None):
        req = urllib.request.Request(API + path, data=data, method=method, headers={
            "api-key": key, "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "AISocialPulseBriefing/1.0"})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:  # Netzwerkfehler nicht als Absturz behandeln
            return None, f"{type(e).__name__}: {e}"
    return call


def credits(call):
    """Restkontingent laut /account (z.B. Free-Plan: 300 pro Tag). None, wenn nicht abrufbar."""
    st, body = call("GET", "/account")
    if st != 200:
        return None
    try:
        return [{k: p.get(k) for k in ("type", "credits", "creditsType")} for p in json.loads(body).get("plan", [])]
    except json.JSONDecodeError:
        return None


def wait_for_delivery(call, message_id, minutes, result_path, result):
    """Pollt die Events-API, bis 'delivered' oder ein Fehler-Event kommt oder die Zeit abläuft."""
    q = urllib.parse.quote(message_id, safe="")
    deadline = time.time() + minutes * 60
    start, i = time.time(), 0
    while True:
        st, ev = call("GET", f"/smtp/statistics/events?limit=20&messageId={q}")
        try:
            events = json.loads(ev).get("events", []) if st == 200 else []
        except json.JSONDecodeError:
            events = []
        names = [e.get("event") for e in events]
        i += 1
        print(f"Event-Check {i} (+{(time.time() - start) / 60:.1f} min): HTTP {st}, Events {names}")
        result.update(events=events, delivered="delivered" in names, checks=i,
                      last_check_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        if result_path:
            json.dump(result, open(result_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if result["delivered"] or any(n in FINAL_BAD for n in names) or time.time() >= deadline:
            break
        time.sleep(10 if time.time() - start < 120 else 60)
    if result["delivered"]:
        print("== Zustellung: DELIVERED")
    else:
        print("== Zustellung: noch kein 'delivered'-Event. NICHT erneut senden – später mit "
              f"--check \"{message_id}\" weiterprüfen (die Events-API kann deutlich hinterherhängen).")
    for e in result["events"]:
        print("   ", {k: e.get(k) for k in ("event", "date", "email", "reason")})
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="Ausgabeordner von render_briefing.py (für den Versand Pflicht)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--wait", type=float, default=8.0, help="Minuten für die Zustellprüfung (Standard 8)")
    ap.add_argument("--check", metavar="MESSAGE_ID", help="nur Zustellung einer bereits gesendeten Mail prüfen")
    a = ap.parse_args()

    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("ABBRUCH: BREVO_API_KEY ist nicht gesetzt.")
    if not key.startswith("xkeysib-"):
        sys.exit("ABBRUCH: BREVO_API_KEY beginnt nicht mit 'xkeysib-' (evtl. SMTP-Key 'xsmtpsib-').")
    call = make_call(key)

    if a.check:
        path = os.path.join(a.out, "check_result.json") if a.out else None
        result = {"messageId": a.check, "events": [], "delivered": False}
        r = wait_for_delivery(call, a.check, a.wait, path, result)
        sys.exit(0 if r["delivered"] else 3)

    if not a.out:
        sys.exit("ABBRUCH: --out fehlt (Ordner mit briefing.html, briefing.txt und meta.json).")
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
    if len(html_body.encode("utf-8")) > 102 * 1024:
        print("Hinweis: HTML über 102 KB – Gmail würde die Mail kürzen (Outlook nicht).")
    plans = credits(call)
    print(f"Kontingent: {plans if plans is not None else 'nicht abrufbar'}")
    if plans and any(p.get("creditsType") == "sendLimit" and p.get("credits") == 0 for p in plans):
        sys.exit("ABBRUCH: Tageskontingent laut /account erschöpft – nicht senden, im Abschlussbericht melden.")
    if a.dry_run:
        print("DRY-RUN: Key-Format ok, nichts gesendet.")
        return

    payload = json.dumps({
        "sender": {"email": cfg["BRIEFING_FROM"], "name": cfg["BRIEFING_FROM_NAME"]},
        "to": [{"email": cfg["BRIEFING_TO"]}],
        "subject": subject, "htmlContent": html_body, "textContent": text_body,
    }).encode("utf-8")

    status, body, message_id = None, "", None
    for attempt in range(1, 5):
        status, body = call("POST", "/smtp/email", payload)
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
    path = os.path.join(a.out, "send_result.json")
    json.dump(result, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    wait_for_delivery(call, message_id, a.wait, path, result)


if __name__ == "__main__":
    main()
