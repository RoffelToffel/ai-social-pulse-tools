# AI Social Pulse – Werkzeuge

Getestete Helfer für die tägliche Routine „AI Social Pulse“ (Stand 01.11. und 02.11.2026).
Die Routine findet dieses Repo im Arbeitsverzeichnis, liest diese Datei und nutzt die
Skripte, statt sie in jedem Lauf neu zu bauen. Der Routine-Prompt liegt in `PROMPT.md`.

## Einbindung (einmalig)

1. Privates GitHub-Repo anlegen, z. B. `ai-social-pulse-tools`, und den Inhalt dieses
   Ordners hochladen (ohne `out/` und `.runtime/`, die stehen in `.gitignore`).
2. Das Repo in der Cloud-Umgebung der Routine als Quelle hinzufügen, damit es bei jedem
   Lauf geklont wird: https://code.claude.com/docs/en/claude-code-on-the-web
3. Den Prompt aus `PROMPT.md` in die Routine übernehmen. `PROMPT.md` ist die maßgebliche
   Fassung: Änderungen dort vornehmen und danach in die Routine kopieren, damit beide nicht
   auseinanderlaufen. Veränderliche Angaben (welche Quelle gerade gesperrt ist) stehen hier
   im Abschnitt „Quellenstatus“ und in `config/`.
4. Environment-Variablen bleiben wie bisher: `BREVO_API_KEY`, `BRIEFING_FROM`,
   `BRIEFING_FROM_NAME`, `BRIEFING_TO`. Der API-Key gehört nie ins Repo.

## Ablauf eines Laufs

```bash
cd <repo>
bash setup.sh                                    # Playwright, Chromium, SPKI-Pin, JETZT
python3 -I tools/brevo_history.py window         # JETZT, Fensterstart/-ende, extended (früherer Tag maßgeblich)
python3 -I tools/brevo_history.py recent --days 7 --out-dir out/hist   # Abgleich: Texte der letzten 7 Briefings

# Entdecken
python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/news.json \
    --file config/feeds_international.txt --file config/feeds_dach.txt \
    --file config/feeds_logistik.txt --file config/feeds_security.txt
python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/discovery.json --file config/discovery_gnews.txt
python3 -I tools/techmeme_links.py               # Original-URLs – Datum in der URL prüfen!
python3 -I tools/hn.py search <START> 20 AI OpenAI Anthropic Claude Gemini DeepSeek LLM
for sub in $(grep -v '^#' config/subreddits.txt); do   # je Sub: neueste und stärkste Posts
  python3 -I tools/feeds.py --now <JETZT> --since <START> --out out/reddit_$sub.json \
      "https://www.reddit.com/r/$sub/new.rss?limit=100" "https://www.reddit.com/r/$sub/top/.rss?t=day"
  sleep 3
done

# Verifizieren
node tools/browser/batchmeta.js out/verify_urls.txt out/verify.json 4 8   # Zeitstempel + Absätze
node tools/browser/gh_commits.js https://github.com/<owner>/<repo>/commits/main
node tools/browser/links.js <artikel-url> "<regex für Primärquelle>"

# Social
python3 -I tools/hn.py item <id> 40
node tools/browser/browse.js reddit https://www.reddit.com/comments/<id>/
python3 -I tools/reddit_links.py "https://www.reddit.com/r/<sub>/new.rss?limit=100" <post_id>
node tools/browser/links.js <artikel-url> "x\\.com|twitter\\.com"   # X-Post hinter einer Meldung finden
python3 -I tools/x_post.py https://x.com/<user>/status/<id>
python3 -I tools/bsky.py "<Begriff>" --since-unix <START>
node tools/browser/browse.js heise <heise-artikel-url> 2500 8       # heise-Forum: Threads + erste Beiträge

# Bauen, prüfen, senden
#   -> out/briefing.json schreiben (Schema unten, Beispiel: examples/briefing_2026-11-01.json)
python3 -I tools/refresh_social.py --from-briefing out/briefing.json --out out/social.json
python3 -I tools/render_briefing.py out/briefing.json --social out/social.json --out out/
python3 -I tools/send_brevo.py --out out/        # sendet nur bei bestandenem QA, prüft bis zu 8 min
python3 -I tools/send_brevo.py --check "<Message-Id>" --wait 25 --out out/   # bei Bedarf im Hintergrund
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
| `tools/brevo_history.py` | Versand-Historie: `window` (Fenster aus dem letzten Briefing eines früheren Tages), `content` (Inhalt eines Briefings), `recent` (Texte der letzten N Tage für den Abgleich) |
| `tools/refresh_social.py` | Holt alle Social-Zahlen zu den Platzhaltern im Briefing-JSON (HN, Reddit, GitHub, Bluesky, X) |
| `tools/render_briefing.py` | Briefing-JSON → Outlook-HTML + Plaintext + `meta.json`, inklusive QA-CHECK |
| `tools/send_brevo.py` | Versand über die Brevo-HTTPS-API, Retries, Kontingent-Anzeige, Zustellprüfung (`--wait`, `--check`); `--dry-run` |
| `tools/browser/*.js` | Playwright-Helfer (`browse.js` mit den Modi text, html, meta, reddit und heise; `batchmeta.js`; `gh_commits.js`; `links.js`), gemeinsamer Start in `common.js`; `meta` und `batchmeta` fallen bei Seiten ohne `<p>`-Absätze auf den Text des Artikel-Containers zurück (Feld `parasSource`) |
| `config/*` | Feed-Listen (international, DACH, Logistik, Security), Google-News-Abfragen, Subreddits, Fallback-Adressen |

## Briefing-JSON

```jsonc
{
  "date": "01.11.2026",                      // TT.MM.JJJJ (deutsches Datum)
  "now_utc": "2026-11-01T10:32:14Z",          // JETZT aus Schritt 1 = Fensterende (Redaktionsschluss)
  "window_start_utc": "2026-10-31T10:32:14Z", // aus brevo_history.py window
  "window_extended": false,                   // optional: "extended" aus brevo_history.py window
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
„24 Punkte/h“, `{rd:ID}` → Reddit-Punkte/Kommentare, `{gh:owner/repo}` → Sterne/Forks,
`{bs:handle/rkey}` → „91 Likes / 27 Reposts“ (Bluesky; `rkey` ist der letzte Teil der
Post-URL), `{x:user/statusid}` → „1106 Likes / 461 Reposts“ (X über fxtwitter).
Platzhalter funktionieren in allen Texten, auch in der TL;DR. Zahlen ohne Platzhalter (etwa
aus Medienberichten) frischt niemand auf – dann den Stand im Methodik-Block nennen.

Zeitstempel werden immer in UTC angegeben; der Renderer zeigt deutsche Ortszeit (MEZ/MESZ
automatisch), das Alter zum Versandzeitpunkt, die Belegstufe (✅ 🟡 🔶) und 🔒 bei Paywall.

## Zeitfenster

Fensterstart = früherer Zeitpunkt aus (JETZT − 24 h) und der Versandzeit des letzten
Briefings eines früheren Tages, nie weiter zurück als JETZT − 72 h. Fensterende = JETZT aus
Schritt 1 (Redaktionsschluss); was während der Recherche erscheint, kommt ins nächste
Briefing. „Erweitert“ heißt das Fenster nur, wenn es mehr als 24 h + 6 min umfasst – diese
Regel nutzen `brevo_history.py` (`extended`) und `render_briefing.py` (`window_extended`
bzw. dieselbe Schwelle) gemeinsam. Dann heißt die Sektion „🟢 Frisch (seit …)“ und der Kopf
nennt die Länge („erweitert auf 26,5 h“).

## QA-CHECK (in `render_briefing.py`)

Exit-Code 2 und kein Versand, wenn:
- ein Eintrag in Karten, Kurzmeldungen oder Radar keinen Zeitstempel im Fenster hat (vor
  Fensterbeginn oder nach `now_utc` = Fensterende), keinen Quellenlink, kein Label oder keine
  Belegstufe,
- ein Inhalt nur über Aggregatoren belegt ist,
- eine Karte keine P&P-Relevanz, Meinung oder Social-Puls hat oder eine Ampel ohne Basis,
- ein Unternehmen mehr als eine Hauptkarte bekommt oder „Läuft noch“ mehr als 2 Einträge hat,
- ein mögliches wörtliches Personenzitat auftaucht (Name + Verb des Sagens + Anführungszeichen),
- `social.json` älter als 10 Minuten ist (mit `--preview` nur Warnung, dann ist der Versand gesperrt),
- das HTML Flexbox/Grid oder Bilder enthält.

Längere Zitate ohne erkannten Personenbezug werden zur manuellen Prüfung aufgelistet. Wörtliche
Personenzitate sind nie erlaubt, auch nicht aus live geprüften Originalen; die Heuristik erkennt
nicht jeden Fall. Die Offenlegung (Claude ist ein Anthropic-Modell) steht immer im Briefing.

Am 01.11.2026 getestet: Rendering des Beispiels (QA bestanden, Darstellung Desktop/Mobil),
Negativtests (altes Datum, doppelte Firma, Personenzitat, nur Aggregator, 3× Läuft noch,
veraltete Social-Zahlen) und `send_brevo.py --dry-run`. Der echte Versand mit demselben
API-Aufruf lief am selben Tag mit HTTP 201 und „delivered“.
Am 02.11.2026 zusätzlich getestet: Zeitstempel nach Fensterende (QA-Fehler), Erweitert-Regel
mit und ohne `window_extended`, Bluesky-/X-/HN-Platzhalter mit `refresh_social.py`,
`send_brevo.py --check` und `--dry-run` mit Kontingent-Anzeige, `brevo_history.py recent`,
`browse.js heise` und der Text-Rückfall von `batchmeta.js` (Phoronix, Security Affairs).

## Quellenstatus (Stand 02.11.2026)

**Funktionieren:** alle Feeds in `config/` (Ausnahme unten), Hacker-News-APIs, Reddit (RSS
inkl. `top/.rss?t=day` und Browser), fxtwitter-API, Bluesky über `api.bsky.app` (Suche,
`getProfile`, `getPosts`), Yonhap, The Star (Reuters-Spiegelung), GitHub-Webseiten im
Browser, Brevo-API (Versand, Events, Historie, Kontingent), lore.kernel.org (Atom-Suche, z. B.
`https://lore.kernel.org/lkml/?q=f%3Atorvalds+d%3A20261101..20261102&x=A`, und `/raw`-Mails),
WordPress-API für wordpress.com-Blogs (`https://public-api.wordpress.com/rest/v1.1/sites/<blog>/posts/`),
Hugging-Face-API (`https://huggingface.co/api/models/<owner>/<repo>` mit `createdAt`),
heise-Forum im Browser.

**Wackelig:** ZDNet-RSS (01.11. ok, 02.11. HTTP 403); heise.de- und 404media.co-Artikelseiten
im Browser gelegentlich Verbindungsabbruch (die Feeds gehen); Handelsblatt-Artikel wechseln
im Tagesverlauf Titel und Aufbau.

**Gesperrt oder nicht auswertbar:** reuters.com, cnbc.com, axios.com, telegraph.co.uk (Akamai),
coindesk.com (Vercel), wsj.com, seekingalpha.com, dealroom.co, mixed-news.com, cbs19.tv,
help.openai.com und openai.com/index/* (Cloudflare), bloomberg.com-Artikelseiten
(Bot-Check 403; das Bloomberg-RSS geht), GitHub-API und github.com-Atom-Feeds
(Proxy-Policy), public.api.bsky.app (403), dvz.de-RSS (404), group.dhl.com-Presse-RSS (Timeout);
seit 02.11. zusätzlich: terrytao.wordpress.com im Browser (Bot-Check; WordPress-API nutzen),
labs.cloudsecurityalliance.org und restofworld.org (Bot-Check), golem.de-Artikelseiten
(Einwilligungsseite; Teaser aus dem Feed nutzen), deutschlandfunk.de und zeit.de (Artikeltext
nicht extrahierbar), kep-aktuell.de-RSS (502). Für BSI und Bundesnetzagentur ist noch kein
funktionierender Feed bekannt.

## Stolpersteine

- **Google News:** pubDate ist kein Beleg. Am 01.11.2026 kamen Archivartikel mit aktuellem
  Datum (ABC vom 13.04., Stocktwits vom 22.07., Reuters-Archiv).
- **Techmeme:** spült am Wochenende Tage alte Meldungen hoch; das Datum steht oft in der
  Original-URL (`/2026/10/29/`). Rund um die US-Zeitumstellung können Offsets falsch sein.
- **Hersteller-Research kommt verspätet in den Medien an:** Am 02.11.2026 liefen ein
  Unit-42-Bericht vom 15.10., eine Chainalysis-Stellungnahme vom 30.10. und ein
  CrowdStrike-Befund vom 29.10. als „neu“. Datum immer im Blog des Herstellers prüfen.
- **Gastbeiträge:** Blog-Inhaber ist nicht gleich Autor (02.11.: Frank Calegari auf Terence
  Taos Blog). Autor im Beitrag bzw. in der WordPress-API prüfen.
- **Reddit 429** ist ein Rate-Limit der geteilten IP, kein Block: 20–30 s warten.
- **Bluesky:** `getPosts` braucht DIDs; mit Handles in `at://`-URIs kommt HTTP 500.
  `refresh_social.py` löst Handles per `getProfile` auf.
- **heise-Forum:** `data-mysql-beautify-date` ist UTC, das `title`-Attribut Ortszeit.
  Autorennamen nicht ins Briefing übernehmen (`browse.js heise` gibt sie nicht aus).
- **Brevo-Events hängen manchmal hinterher:** Am 02.11.2026 war die Mail nach 3 s zugestellt,
  die Events-API zeigte „delivered“ aber erst nach ~22 min (am 01.11. nach ~60 s). Nach
  HTTP 201 nie erneut senden; das Tageskontingent unter `/v3/account` sinkt schon mit der
  Annahme. Mit `send_brevo.py --check` später weiterprüfen.
- **Proxy-Status:** `recentRelayFailures` kann harmlose Einträge von eingebetteten
  Seitenressourcen enthalten (Plain-HTTP-Requests, Werbe-Hosts).
- **Brevo** schreibt den Gmail-Absender in der Historie auf `…@<id>.brevosend.com` um. Das ist erwartet.
- **Manuelle Testläufe** am selben Tag ignoriert `brevo_history.py` für Fenster und Abgleich.
- **Mailgröße:** Gmail kürzt HTML über ~102 KB (Outlook nicht); `send_brevo.py` weist darauf hin.

## Sicherheit

- Der API-Key wird nur aus `BREVO_API_KEY` gelesen und nie ausgegeben oder gespeichert.
- Chromium vertraut per SPKI-Pin gezielt nur der Agent-Proxy-CA. Niemals
  `--ignore-certificate-errors` verwenden und niemals `HTTPS_PROXY` entfernen.
- Kein SMTP: Die Ports sind im Container gesperrt, versendet wird nur über die HTTPS-API.
- Arbeitsdateien liegen in `out/` und `.runtime/` (per `.gitignore` ausgeschlossen) und werden
  nie committet; sie enthalten heruntergeladene Fremdinhalte und die Versand-Historie.
