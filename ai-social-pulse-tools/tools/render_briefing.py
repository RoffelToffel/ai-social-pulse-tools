#!/usr/bin/env python3
"""AI Social Pulse – Renderer mit integriertem QA-CHECK (getestet 01.11.2026).

  python3 -I tools/render_briefing.py out/briefing.json --social out/social.json --out out/
  Optionen:
    --preview   Social-Zahlen dürfen älter als 10 Minuten sein (nur Vorschau;
                send_brevo.py verweigert dann den Versand)

Erzeugt out/briefing.html (Outlook-tauglich), out/briefing.txt (Plaintext-Fallback) und
out/meta.json (Betreff, Preheader, QA-Ergebnis). Exit-Code 0 = QA bestanden, 2 = QA-Fehler.
Schema, Mini-Markup ([Text](URL), **fett**, _kursiv_) und Platzhalter ({hn:ID}, {hnp:ID},
{hnrate:ID}, {rd:ID}, {gh:owner/repo}, {bs:handle/rkey}, {x:user/statusid}) sind in README.md
beschrieben.

Zeitfenster: window_start_utc bis now_utc (= JETZT aus Schritt 1, Redaktionsschluss).
Zeitstempel nach now_utc gehören ins nächste Briefing (QA-Fehler). Als „erweitert“ gilt
das Fenster nur, wenn window_extended gesetzt ist oder es mehr als 24 h + 6 min umfasst –
dieselbe Regel wie in brevo_history.py.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")
BRAND = "AI Social Pulse"
SUBJECT_PREFIX = "AI Social Pulse – Dein KI-Briefing für den {date}"
SUBJECT_MAX = 110
SOCIAL_MAX_AGE = dt.timedelta(minutes=10)
WINDOW_END_TOLERANCE = dt.timedelta(minutes=2)
EXTENDED_AFTER = dt.timedelta(hours=24, minutes=6)
FONT = "font-family:'Segoe UI',Arial,Helvetica,sans-serif;"
PALETTE = [("#2563eb", "#eff6ff"), ("#dc2626", "#fef2f2"), ("#7c3aed", "#f5f3ff"), ("#059669", "#ecfdf5"),
           ("#d97706", "#fffbeb"), ("#0891b2", "#ecfeff"), ("#db2777", "#fdf2f8")]
LEVELS = {"primary": ("✅", "Primärquelle"), "secondary": ("🟡", "Sekundärquelle"),
          "aggregator": ("🔶", "nur Aggregator")}
AMPEL = {"red": "🔴 überwiegend kritisch", "yellow": "🟡 gemischt", "green": "🟢 überwiegend positiv"}

PH = re.compile(r"\{(hn|hnp|hnrate|rd|gh|bs|x):([^}\s]+)\}")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITAL = re.compile(r"(?<![\w*])_(?!\s)(.+?)(?<!\s)_(?![\w*])")
QUOTE = re.compile(r"„([^“]{3,300})“|\"([^\"]{3,300})\"")
SPEECH = re.compile(r"\b(sagte|sagt|schrieb|schreibt|erklärte|erklärt|betonte|betont|meinte|meint|"
                    r"twitterte|postete|warnte|warnt)\b", re.I)
NAME = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+\b")


# ------------------------------------------------------------------ helpers
class QA:
    def __init__(self):
        self.errors, self.warnings, self.quotes = [], [], []

    def err(self, m):
        if m not in self.errors:
            self.errors.append(m)

    def warn(self, m):
        if m not in self.warnings:
            self.warnings.append(m)


def parse_utc(s):
    d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d.astimezone(UTC) if d.tzinfo else d.replace(tzinfo=UTC)


def fmt_dt(d):
    loc = d.astimezone(BERLIN)
    zone = "MESZ" if loc.utcoffset() == dt.timedelta(hours=2) else "MEZ"
    return f"{loc:%d.%m.}, {loc:%H:%M} {zone}"


def fmt_hours(h):
    return f"{h:.1f}".replace(".", ",")


def is_extended(data, now, start):
    flag = data.get("window_extended")
    if isinstance(flag, bool):
        return flag
    return (now - start) > EXTENDED_AFTER


def fmt_age(d, ref):
    h = (ref - d).total_seconds() / 3600
    if h < 1:
        return f"vor {max(int(h * 60), 1)} min"
    return f"vor {h:.0f} h" if h < 48 else f"vor {h / 24:.0f} Tagen"


class Ctx:
    def __init__(self, social, ref, qa):
        self.social, self.ref, self.qa = social, ref, qa

    def _ph(self, m):
        kind, key = m.group(1), m.group(2)
        try:
            if kind.startswith("hn"):
                d = self.social["hn"][key]
                if kind == "hn":
                    return f"{d['score']} Punkte / {d['comments']} Kommentare"
                if kind == "hnp":
                    return f"{d['score']} Punkte"
                hrs = max((self.ref - dt.datetime.fromtimestamp(d["time"], UTC)).total_seconds() / 3600, 0.5)
                return f"{d['score'] / hrs:.0f} Punkte/h"
            if kind == "rd":
                d = self.social["reddit"][key]
                return f"{d['score']} Punkte / {d['comments']} Kommentare"
            if kind == "bs":
                d = self.social["bluesky"][key]
                return f"{d['likes']} Likes / {d['reposts']} Reposts"
            if kind == "x":
                d = self.social["x"][key]
                return f"{d['likes']} Likes / {d['reposts']} Reposts"
            d = self.social["github"][key]
            return f"{d['stars']} Sterne, {d['forks']} Forks"
        except (KeyError, TypeError):
            self.qa.err(f"Platzhalter {{{kind}:{key}}} ohne Social-Daten – refresh_social.py ausführen")
            return "n/a"

    def subst(self, s):
        return PH.sub(self._ph, s or "")


def a_tag(url, label):
    return (f'<a href="{html.escape(url, quote=True)}" style="color:#1a56db;text-decoration:underline;">'
            f'{html.escape(label)}</a>')


def _inline(t):
    t = html.escape(t, quote=False)
    return ITAL.sub(r"<i>\1</i>", BOLD.sub(r"<b>\1</b>", t))


def md_html(s, ctx):
    s = ctx.subst(s)
    out, pos = [], 0
    for m in LINK.finditer(s):
        out.append(_inline(s[pos:m.start()]))
        out.append(a_tag(m.group(2), m.group(1)))
        pos = m.end()
    out.append(_inline(s[pos:]))
    return "".join(out)


def md_text(s, ctx):
    s = LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", ctx.subst(s))
    return ITAL.sub(r"\1", BOLD.sub(r"\1", s))


def p(txt, size=14, color="#111827", margin="0 0 10px 0", extra=""):
    return (f'<p style="margin:{margin};font-size:{size}px;line-height:1.55;color:{color};{FONT}{extra}">'
            f"{txt}</p>")


# ------------------------------------------------------------------ QA
def qa_check(data, social, ref, qa, preview):
    for f in ("date", "now_utc", "window_start_utc", "tldr", "cards", "radar", "running", "dropped", "method"):
        if f not in data:
            qa.err(f"Pflichtfeld fehlt: {f}")
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", data.get("date", "")):
        qa.err("date muss TT.MM.JJJJ sein")
    now, start = parse_utc(data["now_utc"]), parse_utc(data["window_start_utc"])
    if not (now - dt.timedelta(hours=72, minutes=5) <= start < now):
        qa.err("window_start_utc muss vor now_utc liegen und höchstens 72 h zurückreichen")

    def check_stamps(kind, item):
        name = f"{kind} „{(item.get('title') or item.get('text') or '?')[:50]}“"
        stamps = item.get("stamps") or []
        if not stamps:
            qa.err(f"{name}: keine Zeitstempel")
        for st in stamps:
            try:
                d = parse_utc(st["utc"])
            except (KeyError, ValueError):
                qa.err(f"{name}: Zeitstempel unlesbar")
                continue
            if not (start - dt.timedelta(minutes=1) <= d <= now + WINDOW_END_TOLERANCE):
                where = "nach Fensterende – gehört ins nächste Briefing" if d > now else "vor Fensterbeginn"
                qa.err(f"{name}: Zeitstempel {st['utc']} liegt außerhalb des Fensters ({where})")
            if not str(st.get("url", "")).startswith("http"):
                qa.err(f"{name}: Quellenlink fehlt")
            if st.get("level") not in LEVELS:
                qa.err(f"{name}: Belegstufe fehlt (primary/secondary/aggregator)")
            if not st.get("label"):
                qa.err(f"{name}: Quellen-Label fehlt")
        if stamps and not any(s.get("level") in ("primary", "secondary") for s in stamps):
            qa.err(f"{name}: Inhalt nur über Aggregator belegt – Primär- oder Sekundärquelle nötig")

    companies = {}
    for c in data.get("cards", []):
        check_stamps("Karte", c)
        t = (c.get("title") or "?")[:50]
        for f in ("title", "company", "relevance", "opinion"):
            if not c.get(f):
                qa.err(f"Karte „{t}“: Feld {f} fehlt")
        if not c.get("body"):
            qa.err(f"Karte „{t}“: body fehlt")
        if c.get("status") not in ("new", "update"):
            qa.err(f"Karte „{t}“: status muss new oder update sein")
        if c.get("status") == "update" and not c.get("update_ref"):
            qa.err(f"Karte „{t}“: update_ref fehlt")
        soc = c.get("social") or {}
        if not soc.get("items"):
            qa.err(f"Karte „{t}“: Social-Puls fehlt")
        if soc.get("ampel") not in AMPEL:
            qa.warn(f"Karte „{t}“: keine Stimmungs-Ampel (nur ok, wenn es keine Social-Resonanz gibt)")
        elif not soc.get("basis"):
            qa.err(f"Karte „{t}“: Ampel ohne Basis (wie viele Kommentare gelesen?)")
        key = (c.get("company") or "").strip().lower()
        companies[key] = companies.get(key, 0) + 1
    for k, n in companies.items():
        if k and n > 1:
            qa.err(f"Mehr als eine Hauptkarte für dasselbe Unternehmen: {k}")
    for s in data.get("shorts", []):
        check_stamps("Kurzmeldung", s)
    for r in data.get("radar", []):
        check_stamps("Radar", r)
    if not data.get("radar") and not data.get("radar_note"):
        qa.err("Radar leer und radar_note fehlt")
    if len(data.get("running", [])) > 2:
        qa.err("„Läuft noch“ hat mehr als 2 Einträge")
    for r in data.get("running", []):
        if not r.get("timeline"):
            qa.warn(f"Läuft noch „{r.get('title', '?')}“: Mini-Zeitleiste fehlt")
    if not data.get("dropped"):
        qa.warn("Liste der aussortierten Themen ist leer")

    fetched = social.get("fetched_utc")
    if not fetched:
        qa.err("social.json ohne fetched_utc")
    elif ref - parse_utc(fetched) > SOCIAL_MAX_AGE:
        msg = f"Social-Zahlen älter als 10 Minuten (Stand {fetched})"
        qa.warn(msg + " – nur Vorschau") if preview else qa.err(msg + " – refresh_social.py erneut ausführen")

    for s in iter_texts(data):
        for m in QUOTE.finditer(s):
            pre = s[max(0, m.start() - 90):m.start()]
            q = m.group(1) or m.group(2)
            if SPEECH.search(pre) and NAME.search(pre):
                qa.err(f"Mögliches wörtliches Personenzitat – sinngemäß wiedergeben: „{q[:60]}“")
            elif len(q.split()) >= 3 and q[:80] not in qa.quotes:  # kurze Begriffe nicht auflisten
                qa.quotes.append(q[:80])
        if "](" in LINK.sub("", s):
            qa.warn(f"Link-Markup nicht erkannt (nur http/https): {s[:60]}")


def iter_texts(data):
    yield from data.get("tldr", [])
    yield data.get("preheader", "")
    for c in data.get("cards", []):
        yield from [c.get("title", ""), c.get("trigger_note", ""), c.get("relevance", ""), c.get("opinion", "")]
        yield from c.get("body", [])
        yield from (c.get("social") or {}).get("items", [])
    for s in data.get("shorts", []) + data.get("radar", []):
        yield from [s.get("text", ""), s.get("social") or "", s.get("relevance") or ""]
    for r in data.get("running", []):
        yield from [r.get("title", ""), r.get("trigger", ""), r.get("text", ""), r.get("social", "")]
        yield from [t.get("event", "") for t in r.get("timeline", [])]
    for d in data.get("dropped", []):
        yield from [d.get("title", ""), d.get("reason", "")]
    yield from data.get("method", [])


# ------------------------------------------------------------------ HTML
def stamps_html(stamps, ctx):
    parts = []
    for st in stamps:
        d = parse_utc(st["utc"])
        icon, name = LEVELS.get(st.get("level"), ("?", "?"))
        lock = " 🔒" if st.get("paywall") else ""
        parts.append(f"📅 {fmt_dt(d)} ({fmt_age(d, ctx.ref)}) · {a_tag(st['url'], st['label'])}{lock} "
                     f'<span title="{name}">{icon}</span>')
    return p(" &nbsp;|&nbsp; ".join(parts), 12, "#4b5563")


def badge(c):
    if c.get("status") == "update":
        return ('<span style="display:inline-block;padding:2px 8px;background-color:#e0e7ff;color:#3730a3;'
                f'font-size:12px;{FONT}">🔄 Update (zuerst im Briefing vom {html.escape(c.get("update_ref", "?"))})</span>')
    return (f'<span style="display:inline-block;padding:2px 8px;background-color:#dcfce7;color:#166534;'
            f'font-size:12px;{FONT}">🆕 Neu</span>')


def box(inner, bg, border, color):
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin-top:10px;border-collapse:collapse;"><tr><td bgcolor="{bg}" '
            f'style="background-color:{bg};border:1px solid {border};padding:10px 12px;">'
            f'{p(inner, 13, color, "0")}</td></tr></table>')


def card_html(c, i, ctx):
    color, bg = c.get("color") or PALETTE[i % len(PALETTE)][0], c.get("bg") or PALETTE[i % len(PALETTE)][1]
    soc = c.get("social") or {}
    ampel = ""
    if soc.get("ampel") in AMPEL:
        ampel = p(f"{AMPEL[soc['ampel']]} · Basis: {md_html(soc.get('basis', ''), ctx)}", 12, "#374151", "0 0 6px 0")
    trigger = ""
    if c.get("trigger_note"):
        trigger = (f'<p style="margin:0 0 10px 0;padding:8px 10px;background-color:#fff7ed;border:1px solid #fdba74;'
                   f'font-size:12px;line-height:1.5;color:#9a3412;{FONT}">⚠️ {md_html(c["trigger_note"], ctx)}</p>')
    body = "".join(p(md_html(x, ctx)) for x in c.get("body", []) if x)
    social = "".join(p("• " + md_html(x, ctx), 13, "#1f2937", "0 0 6px 0") for x in soc.get("items", []))
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 18px 0;border-collapse:collapse;">
 <tr>
  <td width="6" bgcolor="{color}" style="background-color:{color};width:6px;font-size:0;line-height:0;">&nbsp;</td>
  <td bgcolor="{bg}" style="background-color:{bg};padding:16px 18px;">
   {p(badge(c), 12, "#111827", "0 0 6px 0")}
   {p(f"{html.escape(c.get('emoji', ''))} {md_html(c['title'], ctx)}", 18, "#111827", "0 0 6px 0", "font-weight:bold;line-height:1.3;")}
   {stamps_html(c['stamps'], ctx)}
   {trigger}
   {body}
   {p("💬 Social-Puls", 13, "#374151", "12px 0 6px 0", "font-weight:bold;")}
   {ampel}
   {social}
   {box("<b>📦 Relevanz für P&amp;P-IT (Einordnung):</b> " + md_html(c['relevance'], ctx), "#eef2ff", "#a5b4fc", "#312e81")}
   {box("<b>🧭 Meine Meinung:</b> " + md_html(c['opinion'], ctx), "#fefce8", "#fde047", "#713f12")}
  </td>
 </tr>
</table>"""


def rows_html(items, ctx, with_relevance=False):
    out = []
    for it in items:
        soc = "💬 " + md_html(it["social"], ctx) if it.get("social") else "📰 ohne Social-Echo"
        rel = ""
        if with_relevance and it.get("relevance"):
            rel = p("📦 " + md_html(it["relevance"], ctx), 12, "#312e81", "0 0 3px 0")
        out.append(f'<tr><td style="padding:9px 0;border-bottom:1px solid #e5e7eb;">'
                   f'{p(html.escape(it.get("emoji", "")) + " " + md_html(it["text"], ctx), 14, "#111827", "0 0 3px 0")}'
                   f'{stamps_html(it["stamps"], ctx)}{rel}{p(soc, 12, "#374151", "0")}</td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;">' + "".join(out) + "</table>")


def running_html(r, ctx):
    tl = "".join(f'<tr><td valign="top" style="padding:2px 10px 2px 0;white-space:nowrap;font-size:12px;'
                 f'font-weight:bold;color:#374151;{FONT}">{html.escape(t["date"])}</td>'
                 f'<td style="padding:2px 0;font-size:12px;line-height:1.45;color:#374151;{FONT}">'
                 f'→ {md_html(t["event"], ctx)}</td></tr>' for t in r.get("timeline", []))
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:0 0 12px 0;border-collapse:collapse;"><tr><td bgcolor="#f3f4f6" '
            f'style="background-color:#f3f4f6;border:1px solid #d1d5db;padding:12px 14px;">'
            f'{p(md_html(r["title"], ctx), 15, "#374151", "0 0 4px 0", "font-weight:bold;")}'
            f'{p("🗓️ Auslöser: " + md_html(r.get("trigger", ""), ctx), 12, "#6b7280", "0 0 8px 0")}'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 8px 0;">{tl}</table>'
            f'{p(md_html(r.get("text", ""), ctx), 13, "#1f2937", "0 0 6px 0")}'
            f'{p("💬 " + md_html(r.get("social", ""), ctx), 12, "#374151", "0")}</td></tr></table>')


def section(txt, color):
    return p(txt, 20, color, "26px 0 12px 0", "font-weight:bold;")


def build_html(data, ctx, meta):
    now, start = parse_utc(data["now_utc"]), parse_utc(data["window_start_utc"])
    hours = (now - start).total_seconds() / 3600
    extended = is_extended(data, now, start)
    fresh_title = f"🟢 Frisch (seit {fmt_dt(start)})" if extended else "🟢 Frisch (&lt; 24 h)"
    window = f"Fenster {fmt_dt(start)} – {fmt_dt(now)}" + (f" (erweitert auf {fmt_hours(hours)} h)" if extended else "")
    tldr = "".join(p(md_html(t, ctx), 14, "#0f172a", "0 0 7px 0") for t in data["tldr"])
    disclosure = ("ℹ️ Offenlegung: Recherche und Text stammen von Claude, einem KI-Modell von Anthropic. "
                  "Bei Anthropic-Themen besteht ein möglicher Interessenkonflikt; die Einordnung dort ist bewusst "
                  "nüchtern gehalten und folgt denselben Maßstäben wie bei Wettbewerbern.")
    cards = "".join(card_html(c, i, ctx) for i, c in enumerate(data["cards"]))
    shorts = rows_html(data.get("shorts", []), ctx) if data.get("shorts") else p("Keine weiteren Kurzmeldungen.", 13, "#4b5563")
    radar = (rows_html(data["radar"], ctx, with_relevance=True) if data.get("radar") else "") + \
        (p(md_html(data.get("radar_note", ""), ctx), 13, "#374151") if data.get("radar_note") else "")
    running = "".join(running_html(r, ctx) for r in data.get("running", [])) or p("Keine.", 13, "#4b5563")
    dropped = "".join(p(f"✗ <b>{md_html(d['title'], ctx)}</b>: {md_html(d['reason'], ctx)}", 12, "#374151", "0 0 5px 0")
                      for d in data.get("dropped", []))
    method = "".join(p("• " + m, 12, "#4b5563", "0 0 6px 0") for m in meta["method_html"])
    pre = html.escape(meta["preheader"]) + "&zwnj;&nbsp;" * 90
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>{BRAND} – {html.escape(data['date'])}</title>
<style>
:root {{ color-scheme: light; supported-color-schemes: light; }}
@media only screen and (max-width: 640px) {{
  .container {{ width: 100% !important; max-width: 100% !important; }}
  .px {{ padding-left: 14px !important; padding-right: 14px !important; }}
}}
</style></head>
<body style="margin:0;padding:0;background-color:#e5e7eb;">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#e5e7eb;opacity:0;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#e5e7eb" style="background-color:#e5e7eb;">
<tr><td align="center" style="padding:20px 10px;">
<table role="presentation" class="container" width="640" cellpadding="0" cellspacing="0" border="0" style="width:640px;max-width:640px;border-collapse:collapse;">
 <tr><td class="px" bgcolor="#0f172a" style="background-color:#0f172a;padding:22px 24px;">
  {p("AI SOCIAL PULSE", 12, "#93c5fd", "0", "letter-spacing:2px;")}
  {p(f"⚡ Dein KI-Briefing für den {html.escape(data['date'])}", 24, "#ffffff", "6px 0 4px 0", "font-weight:bold;line-height:1.25;")}
  {p(f"{window} · Social-Stand {meta['social_stand']}", 12, "#cbd5e1", "0")}
 </td></tr>
 <tr><td class="px" bgcolor="#ffffff" style="background-color:#ffffff;padding:22px 24px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
   <tr><td bgcolor="#e0f2fe" style="background-color:#e0f2fe;border:2px solid #38bdf8;padding:14px 16px;">
    {p("📌 TL;DR", 15, "#075985", "0 0 8px 0", "font-weight:bold;")}
    {tldr}
   </td></tr>
  </table>
  {p(disclosure, 12, "#6b7280", "14px 0 0 0")}
  {section(fresh_title, "#047857")}
  {cards}
  {p("📰 Kurz notiert", 16, "#047857", "6px 0 8px 0", "font-weight:bold;")}
  {shorts}
  {section("📦 Logistik- &amp; DHL-Radar", "#1d4ed8")}
  {radar}
  {section("🗓️ Läuft noch (älter)", "#4b5563")}
  {running}
  {section("🚫 Vom Frische-Gate aussortiert", "#991b1b")}
  {dropped}
  {section("🔬 Methodik", "#4b5563")}
  {method}
 </td></tr>
 <tr><td class="px" bgcolor="#0f172a" style="background-color:#0f172a;padding:14px 24px;">
  {p(f"{BRAND} · erstellt am {meta['rendered_local']} · Belegstufen: ✅ Primärquelle · 🟡 Sekundärquelle · 🔶 nur Aggregator · 🔒 Paywall/Sperre · Zitate nur sinngemäß, Meinungen gekennzeichnet.", 12, "#94a3b8", "0")}
 </td></tr>
</table>
</td></tr></table>
</body></html>"""


# ------------------------------------------------------------------ TEXT
def stamps_text(stamps, ctx):
    out = []
    for st in stamps:
        d = parse_utc(st["utc"])
        icon, name = LEVELS.get(st.get("level"), ("?", "?"))
        lock = " [Paywall]" if st.get("paywall") else ""
        out.append(f"{fmt_dt(d)} ({fmt_age(d, ctx.ref)}) · {st['label']}{lock} {icon} {name}: {st['url']}")
    return "   " + " | ".join(out)


def build_text(data, ctx, meta):
    now, start = parse_utc(data["now_utc"]), parse_utc(data["window_start_utc"])
    T = lambda s: md_text(s, ctx)
    ext = f" (erweitert auf {fmt_hours((now - start).total_seconds() / 3600)} h)" if is_extended(data, now, start) else ""
    L = [f"{BRAND.upper()} – Dein KI-Briefing für den {data['date']}",
         f"Fenster {fmt_dt(start)} – {fmt_dt(now)}{ext} · Social-Stand {meta['social_stand']}", "", "TL;DR"]
    L += [f"- {T(t)}" for t in data["tldr"]]
    L += ["", "Offenlegung: Recherche und Text stammen von Claude (Anthropic). Bei Anthropic-Themen besteht ein "
              "möglicher Interessenkonflikt.", "", "=== FRISCH ==="]
    for c in data["cards"]:
        tag = "NEU" if c.get("status") == "new" else f"UPDATE (zuerst im Briefing vom {c.get('update_ref', '?')})"
        L += ["", f"{c.get('emoji', '')} {T(c['title'])}  [{tag}]", stamps_text(c["stamps"], ctx)]
        if c.get("trigger_note"):
            L.append("   Hinweis: " + T(c["trigger_note"]))
        L += [T(x) for x in c.get("body", []) if x]
        soc = c.get("social") or {}
        L.append("Social-Puls:" + (f" {AMPEL[soc['ampel']]} · Basis: {T(soc.get('basis', ''))}" if soc.get("ampel") in AMPEL else ""))
        L += [f" - {T(x)}" for x in soc.get("items", [])]
        L += [f"Relevanz für P&P-IT (Einordnung): {T(c['relevance'])}", f"Meine Meinung: {T(c['opinion'])}"]
    L += ["", "Kurz notiert:"]
    for s in data.get("shorts", []):
        L += [f" {s.get('emoji', '')} {T(s['text'])}", stamps_text(s["stamps"], ctx),
              "    Social: " + (T(s["social"]) if s.get("social") else "ohne Social-Echo")]
    L += ["", "=== LOGISTIK- & DHL-RADAR ==="]
    for r in data.get("radar", []):
        L += [f" {r.get('emoji', '')} {T(r['text'])}", stamps_text(r["stamps"], ctx)]
        if r.get("relevance"):
            L.append("    Relevanz: " + T(r["relevance"]))
        L.append("    Social: " + (T(r["social"]) if r.get("social") else "ohne Social-Echo"))
    if data.get("radar_note"):
        L.append(" " + T(data["radar_note"]))
    L += ["", "=== LÄUFT NOCH (älter) ==="]
    for r in data.get("running", []):
        L += ["", T(r["title"]), "   Auslöser: " + T(r.get("trigger", ""))]
        L += [f"   {t['date']} -> {T(t['event'])}" for t in r.get("timeline", [])]
        L += [T(r.get("text", "")), "Social: " + T(r.get("social", ""))]
    L += ["", "=== VOM FRISCHE-GATE AUSSORTIERT ==="]
    L += [f" x {T(d['title'])}: {T(d['reason'])}" for d in data.get("dropped", [])]
    L += ["", "=== METHODIK ==="] + [f" - {m}" for m in meta["method_text"]]
    L += ["", "Belegstufen: ✅ Primärquelle · 🟡 Sekundärquelle · 🔶 nur Aggregator · [Paywall] = Paywall/Sperre"]
    return "\n".join(L)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("briefing")
    ap.add_argument("--social", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    data = json.load(open(a.briefing, encoding="utf-8"))
    social = json.load(open(a.social, encoding="utf-8"))
    ref = dt.datetime.now(UTC)
    qa = QA()
    qa_check(data, social, ref, qa, a.preview)
    ctx = Ctx(social, ref, qa)

    topics = [t for t in data.get("subject_topics", []) if t]
    subject = SUBJECT_PREFIX.format(date=data["date"]) + (": " + ", ".join(topics) if topics else "")
    if not topics:
        qa.warn("subject_topics leer – Betreff ohne Top-Themen")
    if len(subject) > SUBJECT_MAX:
        qa.warn(f"Betreff länger als {SUBJECT_MAX} Zeichen ({len(subject)})")
    fetched = parse_utc(social["fetched_utc"]) if social.get("fetched_utc") else ref
    now, start = parse_utc(data["now_utc"]), parse_utc(data["window_start_utc"])
    sources = [name for key, name in (("hn", "HN-API"), ("reddit", "Reddit-DOM"), ("github", "GitHub"),
                                      ("bluesky", "Bluesky-API"), ("x", "X über fxtwitter")) if social.get(key)]
    ext_note = " – erweitert, weil das letzte Briefing früher verschickt wurde" if is_extended(data, now, start) else ""
    auto_method = [f"Fenster: {fmt_dt(start)} bis {fmt_dt(now)} ({fmt_hours((now - start).total_seconds() / 3600)} h"
                   f"{ext_note}). Alle Zeiten in deutscher Ortszeit.",
                   f"Social-Zahlen ({', '.join(sources) or 'keine Platzhalter'}): Stand {fmt_dt(fetched)}, unmittelbar "
                   f"vor dem Versand aufgefrischt. Stimmungsbilder beruhen auf tatsächlich gelesenen Kommentaren."]
    meta = {
        "subject": subject,
        "preheader": md_text(data.get("preheader") or (data["tldr"][0] if data.get("tldr") else ""), ctx)[:180],
        "social_stand": fmt_dt(fetched),
        "rendered_local": fmt_dt(ref),
        "method_html": [html.escape(m) for m in auto_method] + [md_html(m, ctx) for m in data.get("method", [])],
        "method_text": auto_method + [md_text(m, ctx) for m in data.get("method", [])],
    }
    html_out = build_html(data, ctx, meta)
    text_out = build_text(data, ctx, meta)
    if re.search(r"display\s*:\s*(flex|grid)", html_out, re.I):
        qa.err("HTML enthält Flexbox/Grid")
    if "<img" in html_out.lower():
        qa.err("HTML enthält Bilder – Layout darf nicht von Bildern abhängen")

    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "briefing.html"), "w", encoding="utf-8").write(html_out)
    open(os.path.join(a.out, "briefing.txt"), "w", encoding="utf-8").write(text_out)
    result = {
        "subject": subject, "preheader": meta["preheader"], "date": data["date"],
        "now_utc": data["now_utc"], "window_start_utc": data["window_start_utc"],
        "rendered_utc": ref.isoformat(), "social_fetched_utc": social.get("fetched_utc"),
        "qa_passed": not qa.errors, "preview_only": bool(a.preview),
        "errors": qa.errors, "warnings": qa.warnings, "quotes_for_review": qa.quotes,
        "html_chars": len(html_out), "text_chars": len(text_out),
    }
    json.dump(result, open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Betreff: {subject}")
    print(f"HTML {len(html_out)} Zeichen, Text {len(text_out)} Zeichen -> {a.out}")
    for w in qa.warnings:
        print("WARNUNG:", w)
    for q in qa.quotes:
        print("Zitat prüfen (kein Personenzitat?):", q)
    if qa.errors:
        for e in qa.errors:
            print("QA-FEHLER:", e)
        sys.exit(2)
    print("QA bestanden" + (" (Vorschau – Versand gesperrt)" if a.preview else ""))


if __name__ == "__main__":
    main()
