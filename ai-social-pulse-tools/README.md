# AI Social Pulse – Werkzeuge

Getestete Helfer für die tägliche Routine „AI Social Pulse“ (Stand 01.11.2026).
Die Routine findet dieses Repo im Arbeitsverzeichnis, liest diese Datei und nutzt die
Skripte, statt sie in jedem Lauf neu zu bauen. Der Routine-Prompt liegt in `PROMPT.md`.

## Einbindung (einmalig)

1. Privates GitHub-Repo anlegen, z. B. `ai-social-pulse-tools`, und den Inhalt dieses
   Ordners hochladen (ohne `out/` und `.runtime/`, die stehen in `.gitignore`).
2. Das Repo in der Cloud-Umgebung der Routine als Quelle hinzufügen, damit es bei jedem
   Lauf geklont wird: https://code.claude.com/docs/en/claude-code-on-the-web
3. Den Prompt aus `PROMPT.md` in die Routine übernehmen.
4. Environment-Variablen bleiben wie bisher: `BREVO_API_KEY`, `BRIEFING_FROM`,
   `BRIEFING_FROM_NAME`, `BRIEFING_TO`. Der API-Key gehört nie ins Repo.

## Ablauf eines Laufs

```bash
cd <repo>
bash setup.sh                                    # Playwright, Chromium, SPKI-Pin, JETZT
python3 -I tools/brevo_history.py window         # Zeitfenster + letztes Briefing (früherer Tag)
python3 -I tools/brevo_history.py content <uuid> --out out/prev_briefing.html   # für den Abgleich

# Entdecken
python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/news.json \
    --file config/feeds_international.txt --file config/feeds_dach.txt --file config/feeds_logistik.txt
python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/discovery.json --file config/discovery_gnews.txt
python3 -I tools/techmeme_links.py               # Original-URLs – Datum in der URL prüfen!
python3 -I tools/hn.py search <START> 20 AI OpenAI Anthropic Claude Gemini DeepSeek LLM
python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/reddit_artificial.json \
    "https://www.reddit.com/r/artificial/new.rss?limit=100"          # je Sub aus config/subreddits.txt

# Verifizieren
node tools/browser/batchmeta.js out/verify_urls.txt out/verify.json 4 8   # Zeitstempel + Absätze
node tools/browser/gh_commits.js https://github.com/<owner>/<repo>/commits/main
node tools/browser/links.js <artikel-url> "<regex für Primärquelle>"

# Social
python3 -I tools/hn.py item <id> 40
node tools/browser/browse.js reddit https://www.reddit.com/comments/<id>/
python3 -I tools/reddit_links.py "https://www.reddit.com/r/<sub>/new.rss?limit=100" <post_id>
python3 -I tools/x_post.py https://x.com/<user>/status/<id>
python3 -I tools/bsky.py "<Begriff>" --since-unix <START>

# Bauen, prüfen, senden
#   -> out/briefing.json schreiben (Schema unten, Beispiel: examples/briefing_2026-11-01.json)
python3 -I tools/refresh_social.py --from-briefing out/briefing.json --out out/social.json
python3 -I tools/render_briefing.py out/briefing.json --social out/social.json --out out/
python3 -I tools/send_brevo.py --out out/        # sendet nur bei bestandenem QA
```

Python immer mit `-I` aufrufen (es werden heruntergeladene Daten verarbeitet); deshalb sind
alle Python-Skripte eigenständig und importieren sich nicht gegenseitig.

## Werkzeuge

| Datei | Zweck |
|---|---|
| `setup.sh` | Prüft das vorinstallierte Playwright (nie neu installieren), ermittelt den Chromium-Pfad, berechnet den SPKI-Pin der Proxy-CA, zeigt JETZT und den Status der Variablen |
| `tools/feeds.py` | RSS/Atom per ElementTree (CDATA-sicher), UTC-Normalisierung, Fensterfilter (`--since`/`--hours`), 429-Retry |
| `tools/techmeme_links.py` | Original-Links hinter Techmeme-Einträgen |
| `tools/hn.py` | HN-Suche (Algolia, mit Punkten/h) und Thread mit exaktem Zeitstempel (Firebase) |
| `tools/reddit_links.py` | Externe Links aus Reddit-RSS-Einträgen |
| `tools/x_post.py` | X-Post live über den fxtwitter-Spiegel prüfen (Zeitstempel, Text, Likes) |
| `tools/bsky.py` | Bluesky-Suche ohne Login (`api.bsky.app`) |
| `tools/brevo_history.py` | Versand-Historie: Fenster aus dem letzten Briefing eines früheren Tages, Inhalt alter Briefings |
| `tools/refresh_social.py` | Holt alle Social-Zahlen zu den Platzhaltern im Briefing-JSON (HN, Reddit, GitHub) |
| `tools/render_briefing.py` | Briefing-JSON → Outlook-HTML + Plaintext + `meta.json`, inklusive QA-CHECK |
| `tools/send_brevo.py` | Versand über die Brevo-HTTPS-API, Retries, Zustellprüfung; `--dry-run` |
| `tools/browser/*.js` | Playwright-Helfer (`browse.js`, `batchmeta.js`, `gh_commits.js`, `links.js`), gemeinsamer Start in `common.js` |
| `config/*` | Feed-Listen, Google-News-Abfragen, Subreddits, Fallback-Adressen |

## Briefing-JSON

```jsonc
{
  "date": "01.11.2026",                      // TT.MM.JJJJ (deutsches Datum)
  "now_utc": "2026-11-01T10:32:14Z",          // JETZT
  "window_start_utc": "2026-10-31T10:32:14Z", // aus brevo_history.py window
  "subject_topics": ["DeepSeek-Agent", "KI-Infostealer"],   // Betreff ≤ ca. 110 Zeichen
  "preheader": "Vorschauzeile …",
  "tldr": ["…"],
  "cards": [{                                 // Hauptkarten, max. eine pro Unternehmen
    "status": "new",                          // oder "update" + "update_ref": "31.10."
    "emoji": "🐋", "title": "…", "company": "DeepSeek",
    "stamps": [{"utc": "…Z", "url": "…", "label": "GitHub-Commit",
                "level": "primary", "paywall": false}],   // primary | secondary | aggregator
    "trigger_note": "…",                      // optional: älterer Auslöser mit Datum
    "body": ["…"],
    "social": {"ampel": "red|yellow|green|null", "basis": "ca. 40 von 131 Kommentaren gelesen",
               "items": ["…"]},
    "relevance": "📦 Relevanz für P&P-IT (Einordnung)",
    "opinion": "🧭 Meine Meinung"
  }],
  "shorts": [{"emoji": "…", "company": "…", "text": "…", "stamps": [ … ], "social": "…" | null}],
  "radar": [{"emoji": "…", "company": "…", "text": "…", "stamps": [ … ], "relevance": "…", "social": null}],
  "radar_note": "…",                          // Pflicht, wenn radar leer ist
  "running": [{"title": "…", "trigger": "…", "timeline": [{"date": "26.10.", "event": "…"}],
               "text": "…", "social": "…"}],  // max. 2
  "dropped": [{"title": "…", "reason": "…"}], // vollständig
  "method": ["…"]                             // Fenster und Social-Stand ergänzt der Renderer
}
```

**Mini-Markup** in allen Texten: `[Text](https://url)`, `**fett**`, `_kursiv_`. Alles andere
wird escaped, rohes HTML ist nicht vorgesehen.

**Platzhalter** für Social-Zahlen, die `refresh_social.py` kurz vor dem Versand auffrischt:
`{hn:ID}` → „365 Punkte / 209 Kommentare“, `{hnp:ID}` → „365 Punkte“, `{hnrate:ID}` →
„24 Punkte/h“, `{rd:ID}` → Reddit-Punkte/Kommentare, `{gh:owner/repo}` → Sterne/Forks.

Zeitstempel werden immer in UTC angegeben; der Renderer zeigt deutsche Ortszeit (MEZ/MESZ
automatisch), das Alter zum Versandzeitpunkt, die Belegstufe (✅ 🟡 🔶) und 🔒 bei Paywall.

## QA-CHECK (in `render_briefing.py`)

Exit-Code 2 und kein Versand, wenn:
- ein Eintrag in Karten, Kurzmeldungen oder Radar keinen Zeitstempel im Fenster, keinen
  Quellenlink, kein Label oder keine Belegstufe hat,
- ein Inhalt nur über Aggregatoren belegt ist,
- eine Karte keine P&P-Relevanz, Meinung oder Social-Puls hat oder eine Ampel ohne Basis,
- ein Unternehmen mehr als eine Hauptkarte bekommt oder „Läuft noch“ mehr als 2 Einträge hat,
- ein mögliches wörtliches Personenzitat auftaucht (Name + Verb des Sagens + Anführungszeichen),
- `social.json` älter als 10 Minuten ist (mit `--preview` nur Warnung, dann ist der Versand gesperrt),
- das HTML Flexbox/Grid oder Bilder enthält.

Längere Zitate ohne Personenbezug werden zur manuellen Prüfung aufgelistet. Die Offenlegung
(Claude ist ein Anthropic-Modell) steht immer im Briefing.

Am 01.11.2026 getestet: Rendering des Beispiels (QA bestanden, Darstellung Desktop/Mobil),
Negativtests (altes Datum, doppelte Firma, Personenzitat, nur Aggregator, 3× Läuft noch,
veraltete Social-Zahlen) und `send_brevo.py --dry-run`. Der echte Versand mit demselben
API-Aufruf lief am selben Tag mit HTTP 201 und „delivered“.

## Quellenstatus (Stand 01.11.2026)

**Funktionieren:** alle Feeds in `config/`, Hacker-News-APIs, Reddit (RSS und Browser),
fxtwitter-API, Bluesky über `api.bsky.app`, Yonhap, The Star (Reuters-Spiegelung),
GitHub-Webseiten im Browser, Brevo-API (Versand, Events, Historie).

**Gesperrt:** reuters.com, cnbc.com, axios.com, telegraph.co.uk (Akamai), coindesk.com
(Vercel), wsj.com, seekingalpha.com, dealroom.co, mixed-news.com, cbs19.tv,
help.openai.com und openai.com/index/* (Cloudflare), bloomberg.com-Artikelseiten
(Bot-Check 403; das Bloomberg-RSS geht), GitHub-API und github.com-Atom-Feeds
(Proxy-Policy), public.api.bsky.app (403), dvz.de-RSS (404), group.dhl.com-Presse-RSS (Timeout).

## Stolpersteine

- **Google News:** pubDate ist kein Beleg. Am 01.11.2026 kamen Archivartikel mit aktuellem
  Datum (ABC vom 13.04., Stocktwits vom 22.07., Reuters-Archiv).
- **Techmeme:** spült am Wochenende Tage alte Meldungen hoch; das Datum steht oft in der
  Original-URL (`/2026/10/29/`). Rund um die US-Zeitumstellung können Offsets falsch sein.
- **Reddit 429** ist ein Rate-Limit der geteilten IP, kein Block: 20–30 s warten.
- **Proxy-Status:** `recentRelayFailures` kann harmlose Einträge von eingebetteten
  Seitenressourcen enthalten (Plain-HTTP-Requests, Werbe-Hosts).
- **Brevo** schreibt den Gmail-Absender in der Historie auf `…@<id>.brevosend.com` um. Das ist erwartet.
- **Manuelle Testläufe** am selben Tag ignoriert `brevo_history.py` für Fenster und Abgleich.

## Sicherheit

- Der API-Key wird nur aus `BREVO_API_KEY` gelesen und nie ausgegeben oder gespeichert.
- Chromium vertraut per SPKI-Pin gezielt nur der Agent-Proxy-CA. Niemals
  `--ignore-certificate-errors` verwenden und niemals `HTTPS_PROXY` entfernen.
- Kein SMTP: Die Ports sind im Container gesperrt, versendet wird nur über die HTTPS-API.
