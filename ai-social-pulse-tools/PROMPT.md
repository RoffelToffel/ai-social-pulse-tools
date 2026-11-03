Erstelle ein tägliches "AI Social Pulse" Briefing und versende es als E-Mail.

LESER
Einziger Empfänger arbeitet in der IT der DHL Group, Unternehmensbereich Post & Paket
Deutschland (P&P). Das Briefing liefert KI-Nachrichten plus Social-Stimmung und ordnet
beides für die Konzern-IT eines großen deutschen Paket- und Postdienstleisters ein.
Sprache Deutsch, Du-Ansprache. Ausführlich schreiben — NICHT kürzen.

ABLAUF (in dieser Reihenfolge)
1. JETZT bestimmen: `date -u` (UTC) und `TZ=Europe/Berlin date` (deutsche Ortszeit).
   Heutiges und gestriges Datum notieren. JETZT ist zugleich das Fensterende
   (Redaktionsschluss).
2. Quellen-Setup ausführen (siehe QUELLEN-SETUP; mit Werkzeug-Repo: `bash setup.sh`).
3. Versand-Historie prüfen (siehe VERSAND-HISTORIE): Zeitfenster festlegen, die Briefings
   der letzten 7 Tage für den Abgleich laden.
4. Allgemeine KI-Nachrichten im Fenster sichten -> Themen ableiten.
5. Logistik- & DHL-Radar erstellen (siehe DHL/P&P-RELEVANZ).
6. Pro Thema die Social-Stimmung suchen (siehe SOCIAL-QUELLEN).
7. Mit den Briefings der letzten 7 Tage abgleichen (🆕 neu / 🔄 Update).
8. Social-Zahlen auffrischen (höchstens 10 Minuten vor Versand), Briefing bauen,
   QA-CHECK ausführen.
9. Per Brevo-API versenden und Zustellung verifizieren (nach HTTP 201 nie erneut senden).
10. Abschlussbericht.

════════════════════════════════════════════════════════════════════════
VERSAND-HISTORIE (Brevo-API, getestet am 01.11. und 02.11.2026)
════════════════════════════════════════════════════════════════════════
- Liste:  GET https://api.brevo.com/v3/smtp/emails?email=<BRIEFING_TO>&limit=50&sort=desc
          Header "api-key" wie beim Versand. Liefert je Mail date, subject, uuid.
- Inhalt: GET https://api.brevo.com/v3/smtp/emails/<uuid>
          -> "body" (HTML des versendeten Briefings) und "events".
  (Mit Werkzeug-Repo: `python3 -I tools/brevo_history.py window`, `content <uuid>` und
  `recent --days 7 --out-dir out/hist` für die Texte der letzten 7 Briefings.)
- MASSGEBLICH für das Zeitfenster ist das letzte Briefing eines FRÜHEREN Tages (Datum im
  Betreff vor dem heutigen). Briefings vom selben Tag, z.B. manuelle Testläufe, werden für
  Zeitfenster und Abgleich ignoriert.
- ZEITFENSTER: Fensterstart = der frühere Zeitpunkt aus (JETZT − 24 h) und der Versandzeit
  dieses Briefings, aber nie weiter zurück als JETZT − 72 h. Fensterende = JETZT aus
  Schritt 1. Meldungen, die während der Recherche nach JETZT erscheinen, gehören ins nächste
  Briefing und werden im Methodik-Block genannt. Normalfall also genau 24 h; nach
  ausgefallenen oder früheren Läufen wird die Lücke geschlossen. Das Fenster steht im Kopf
  der Mail. "Erweitert" ist es nur, wenn es mehr als 24 h + 6 min umfasst; dann heißt die
  Sektion "🟢 Frisch (seit <TT.MM., HH:MM>)". (Mit Werkzeug-Repo: now_utc,
  window_start_utc und extended aus `brevo_history.py window` ins Briefing-JSON übernehmen,
  extended als window_extended.)
- ABGLEICH: Themen der Briefings der letzten 7 Tage aus deren body ermitteln, mindestens die
  des letzten Briefings. Bereits behandelte Themen nur mit echter neuer Entwicklung im
  Fenster erneut aufnehmen, dann als "🔄 Update (zuerst im Briefing vom TT.MM.)" mit dem
  Datum der ERSTEN Behandlung. Neue Themen als "🆕". Nichts ohne Neuigkeit wiederholen,
  auch keine Themen von vor 2 bis 6 Tagen.
- Ist die Historie nicht abrufbar: 24-h-Fenster, kein Abgleich, im Methodik-Block vermerken.
- Die Historie zeigt als Absender "…@<id>.brevosend.com": Brevo schreibt Gmail-Absender
  automatisch um. Das ist erwartet und kein Fehler.

════════════════════════════════════════════════════════════════════════
HARTES FRISCHE-GATE (das Wichtigste — keine Ausnahmen)
════════════════════════════════════════════════════════════════════════
"Fenster" meint das unter VERSAND-HISTORIE festgelegte Zeitfenster (Standard 24 h, Ende JETZT).
- DATE-ANCHORED SUCHEN: Hänge das explizite heutige bzw. gestrige Datum an die
  Suchanfragen (z.B. "...June 21, 2026", "...June 20"). Suche zusätzlich nach
  "today"/"last 24 hours"/"breaking".
- KEINE ROUNDUPS: Ignoriere monatliche/wöchentliche Sammelartikel ("June 2026 AI news",
  "this week in AI", "weekly roundup"). Nutze datierte Primärquellen (Newsroom-Posts,
  Press Releases, Blogposts mit Dateline).
- AGGREGATOREN NUR ZUR ENTDECKUNG, NIE ALS BELEG: aiweekly.co, techmeme.com,
  llm-stats.com, Google News oder AI-Daily-Digest-Repos eignen sich, um Kandidaten zu
  FINDEN. Zeitstempel und Fakten immer an der Primär- oder Erstmeldung prüfen.
  * GOOGLE NEWS: pubDate ist kein Beleg. Am 01.11.2026 kamen Archivartikel mit
    aktuellem Datum (ABC-Artikel vom 13.04., Stocktwits-Artikel vom 22.07.,
    Reuters-Archivmeldungen).
  * TECHMEME: spült besonders am Wochenende Meldungen hoch, die Tage alt sind
    (01.11.2026: Deals vom 27. und 29.10.). Datum in der Original-URL prüfen
    (z.B. /2026/10/29/). Rund um die US-Zeitumstellung kann der Feed Zeiten mit
    falschem Offset labeln.
- HERSTELLER-RESEARCH: Berichte von Security- und Forschungsfirmen (Unit 42, Talos,
  CrowdStrike, Chainalysis u.a.) tauchen in Medien oft erst Tage später auf. Am 02.11.2026
  liefen so ein Unit-42-Bericht vom 15.10., eine Chainalysis-Stellungnahme vom 30.10. und
  ein CrowdStrike-Befund vom 29.10. als "neu". Datum immer im Blog des Herstellers prüfen.
- TIMESTAMP-PFLICHT: Für JEDEN Kandidaten einen konkreten Veröffentlichungs-Zeitstempel
  feststellen. Fundstellen: meta article:published_time, JSON-LD datePublished,
  <time datetime>; bei GitHub relative-time[datetime] auf /commits/main; bei Mails auf
  lore.kernel.org der Date-Header (/raw); bei wordpress.com-Blogs die WordPress-API; bei
  Modell-Repos auf Hugging Face die API (createdAt, lastModified).
  Nur tages- oder monatsgenaue Daten reichen nicht. Kein belegbarer Stempel im Fenster
  -> NICHT als frische News aufnehmen. Im Zweifel weglassen.
- VORSICHT BEI "vor X Stunden"-ANGABEN: Relative Zeitangaben auf Aggregatoren beziehen
  sich oft auf den Aggregator-Pickup, nicht auf die Originalmeldung.
- ACHTUNG FALLE: Ein frischer Forums-Thread beweist NICHT, dass die zugrunde liegende
  Meldung frisch ist. Ein alter Blogpost, der heute auf Hacker News hochgespült wird,
  gehört in "Läuft noch" — mit beiden Daten ausgewiesen. (Gegenprobe: Ist die Reaktion
  frisch, der Auslöser aber alt, darf das Thema frisch laufen — dann MIT explizitem
  Hinweis auf das Auslöser-Datum.)
- SICHTBAR DATIEREN: Jeder Eintrag trägt absolute Zeit, relatives Alter zum
  Versandzeitpunkt, Quellenlink und Belegstufe, z.B.
  "📅 31.10., 13:05 MEZ (vor 21 h) · Quelle ✅".
- ZEITZONEN NORMALISIEREN: Feeds liefern gemischte Zonen (Techmeme -0400/-0500,
  US-Medien ET/PT). Immer nach UTC umrechnen, dann das Alter bestimmen. Im Briefing
  einheitlich deutsche Ortszeit: MEZ (UTC+1) im Winter, MESZ (UTC+2) im Sommer — per
  `TZ=Europe/Berlin date +%Z` bestimmen und korrekt beschriften.
- KLARE TRENNUNG: "🟢 Frisch" zuerst. Wichtige ältere Themen NUR in der separaten
  Sektion "🗓️ Läuft noch (älter)" mit max. 2 Einträgen und expliziten Daten.
- QUALITÄT > QUANTITÄT: Passieren weniger als 3 Themen das Gate, fällt das Briefing
  entsprechend kürzer aus. NIEMALS mit alten Themen auffüllen. Ansonsten gilt: nicht kürzen.
- AUSSORTIERTES AUSWEISEN: Alle prominenten Themen, die wegen des Zeitfensters oder
  fehlender Belege verworfen wurden, vollständig mit Datum und Grund nennen.

════════════════════════════════════════════════════════════════════════
QUELLEN-SETUP (einmal zu Beginn jedes Laufs)
════════════════════════════════════════════════════════════════════════
0) WERKZEUG-REPO: Das private Repo "ai-social-pulse-tools" enthält die am 01.11. und
   02.11.2026 getesteten Helfer. Finden:
     find / -maxdepth 4 -type d -name ai-social-pulse-tools 2>/dev/null | head -1
   Ist es vorhanden:
   - zuerst README.md lesen, dann `bash setup.sh` ausführen (ersetzt die Schritte 1–3),
   - die Skripte nutzen: tools/feeds.py, techmeme_links.py, hn.py, reddit_links.py,
     x_post.py, bsky.py, brevo_history.py, refresh_social.py, send_brevo.py,
     tools/browser/*.js (browse.js heise für das heise-Forum),
   - die Feed-Listen in config/ verwenden (international, DACH, Logistik, Security),
   - das Briefing als JSON schreiben (Schema in README.md, Beispiel in examples/) und mit
     tools/render_briefing.py rendern; tools/send_brevo.py sendet nur bei bestandenem QA.
   Fehler in Repo-Skripten im Abschlussbericht melden; nötige Korrekturen nur als Kopie im
   Scratchpad, nicht stillschweigend im Repo.
   Fehlt das Repo: Helfer wie in den Schritten 1–3 beschrieben neu bauen.

Viele Newsseiten blockieren die Rechenzentrums-IP dieses Containers (403). Das ist NICHT
der Agent-Proxy — `curl -sS "$HTTPS_PROXY/__agentproxy/status"` zeigt in der Regel keine
relevanten `recentRelayFailures` (harmlose Einträge von eingebetteten Seitenressourcen
sind möglich). Es hilft nur ein anderer Zugangsweg.

1) Playwright: das vorinstallierte globale Playwright verwenden; vorher prüfen mit
   `node -e "require('playwright')"`. NICHT neu installieren, kein `playwright install`.
   CHROME=$(find /opt/pw-browsers -maxdepth 3 -name chrome -type f | head -1)
   (01.11.2026: /opt/pw-browsers/chromium-1243/chrome-linux64/chrome)
   Nur falls require scheitert: PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install playwright
   --no-audit --no-fund und executablePath=$CHROME setzen.

2) Proxy-CA als SPKI-Pin berechnen — Chromium vertraut ihr sonst nicht:
   openssl x509 -in /root/.ccr/agent-proxy-ca.crt -pubkey -noout \
     | openssl pkey -pubin -outform der \
     | openssl dgst -sha256 -binary | openssl enc -base64 > spki.txt
   Start dann mit: --no-sandbox --ignore-certificate-errors-spki-list=<spki>
   WICHTIG: Das vertraut gezielt NUR dieser einen CA. Niemals
   --ignore-certificate-errors verwenden und niemals HTTPS_PROXY unsetzen.

3) Feed-Parser als EIGENE Datei schreiben (nicht inline via `python3 -c`):
   - Verschachteltes Shell-Quoting zerstört das Skript zuverlässig.
   - Feeds mit echtem XML-Parsing lesen (ElementTree), NICHT mit Regex: `<[^>]+>`
     verschluckt ganze CDATA-Titel (Bloomberg, Guardian, TechCrunch u.a.) still.
   - RSS (<item>/<pubDate>) und Atom (<entry>/<published>/<updated>) unterstützen.
   - Nach UTC normalisieren, auf das Fenster filtern.

════════════════════════════════════════════════════════════════════════
NACHRICHTENQUELLEN (Stand geprüft 02.11.2026 — spart dir das Durchprobieren)
════════════════════════════════════════════════════════════════════════
Der jeweils aktuelle Erreichbarkeitsstatus steht im Werkzeug-Repo (README.md, Abschnitt
"Quellenstatus", und die Listen in config/). Er hat Vorrang vor dieser Liste.

INTERNATIONAL (RSS/Atom, mit beschreibendem User-Agent abrufen):
  https://www.techmeme.com/feed.xml                     (minutengenaue pubDate)
  https://feeds.bloomberg.com/technology/news.rss
  https://feeds.bloomberg.com/markets/news.rss          (Markt-/Chip-Reaktionen)
  https://feeds.nbcnews.com/nbcnews/public/tech
  https://www.theregister.com/headlines.atom
  https://www.theguardian.com/technology/artificialintelligenceai/rss
  https://techcrunch.com/category/artificial-intelligence/feed/
  https://arstechnica.com/ai/feed/
  https://www.wired.com/feed/tag/ai/latest/rss
  https://www.zdnet.com/topic/artificial-intelligence/rss.xml   (wackelig: 02.11.2026 403)
  https://www.theverge.com/rss/index.xml
  https://openai.com/news/rss.xml                       (Primärquelle)
  https://hnrss.org/frontpage?points=50
  https://en.yna.co.kr/RSS/news.xml                     (Yonhap: Korea, Chips, Exporte)
  https://www.phoronix.com/rss.php                      (Open Source, Kernel, KI-Last in Projekten)

DEUTSCH/DACH:
  https://www.heise.de/rss/heise-atom.xml
  https://rss.golem.de/rss.php?feed=ATOM1.0
  https://t3n.de/rss.xml
  https://netzpolitik.org/feed/
  https://www.handelsblatt.com/contentexport/feed/schlagzeilen   (auch /top-themen)
  Für BSI und Bundesnetzagentur ist kein funktionierender Feed bekannt -> über Google News
  entdecken und auf der Behördenseite prüfen.

SECURITY:
  https://www.heise.de/security/rss/news-atom.xml
  https://www.bleepingcomputer.com/feed/
  https://feeds.feedburner.com/TheHackersNews
  https://securityaffairs.com/feed
  https://www.theregister.com/security/headlines.atom
  (Hersteller-Research hier immer am Original datieren, siehe FRISCHE-GATE.)

LOGISTIK:
  https://www.freightwaves.com/news/feed
  https://www.supplychaindive.com/feeds/news/
  https://theloadstar.com/feed/
  https://www.logistik-heute.de/rss.xml
  https://postandparcel.info/feed/                      (Post- und Paketbranche)
  https://www.parcelandpostaltechnologyinternational.com/feed
  Google News zur Entdeckung, z.B.:
  https://news.google.com/rss/search?q=%22Deutsche+Post%22+OR+DHL+when:1d&hl=de&gl=DE&ceid=DE:de
  https://news.google.com/rss/search?q=DHL+AI+when:1d&hl=en-US&gl=US&ceid=US:en
  https://news.google.com/rss/search?q=logistics+AI+when:1d&hl=en-US&gl=US&ceid=US:en
  NICHT FUNKTIONIEREND: dvz.de/rss.xml (404), Presse-RSS von group.dhl.com (Timeout).
  -> DHL-Pressemitteilungen über Google News entdecken und auf group.dhl.com im Browser
     prüfen.

BLOOMBERG: Das RSS liefert Titel und minutengenaue pubDate. Artikelseiten liefern seit
01.11.2026 auch im Browser 403 (Bot-Check). Inhalt nur über Spiegelungen; sonst den Titel
als Aggregator-Angabe kennzeichnen.

GESPERRT: reuters.com, cnbc.com, axios.com (HTML 401/403, eigene RSS-Endpunkte 403/404,
Browser 403; Reuters hat sein RSS eingestellt). Zusätzlich gesperrt am 01.11.2026:
telegraph.co.uk (Akamai), coindesk.com (Vercel), wsj.com, seekingalpha.com, dealroom.co,
mixed-news.com, cbs19.tv, help.openai.com und openai.com/index/* (Cloudflare),
bloomberg.com-Artikelseiten, GitHub-API und github.com-Atom-Feeds (Proxy-Policy;
GitHub-Webseiten funktionieren im Browser). Weitere Sperren seit 02.11.2026: siehe
README.md im Werkzeug-Repo.
  -> Für Entdeckung + Zeitstempel: Google News RSS, z.B.
     https://news.google.com/rss/search?q=site:reuters.com+AI&hl=en-US&gl=US&ceid=US:en
  -> Artikeltext über eine erreichbare Spiegelung belegen: thestar.com.my (am 01.11.2026
     bestätigt), channelnewsasia.com und theedgemalaysia.com (Reuters-Texte, 02.11.2026
     bestätigt), finance.yahoo.com, tomshardware.com, biztoc.com
     (investing.com und qz.com blocken inzwischen ebenfalls).
  -> Ohne Spiegelung: Thema NICHT als belegt behandeln. Ein Google-News-Titel allein ist
     eine Aggregator-Angabe, kein Beleg.

════════════════════════════════════════════════════════════════════════
SOCIAL-QUELLEN
════════════════════════════════════════════════════════════════════════
HACKER NEWS — zuverlässigste live prüfbare Quelle. APIs nutzen, nicht die Website:
  * Exakter Zeitstempel eines Posts:
    https://hacker-news.firebaseio.com/v0/item/<ID>.json  (Feld "time", UNIX-UTC)
  * Stories im Fenster finden:
    https://hn.algolia.com/api/v1/search_by_date?query=<Begriff>&tags=story
    &numericFilters=created_at_i><UNIX-Zeitstempel>,points>20
    (Mehrere Einzelbegriffe abfragen; OR-Syntax liefert dort keine Treffer.)
  * Thread samt Kommentaren: https://hn.algolia.com/api/v1/items/<ID>
  Punkte, Kommentarzahl und Tempo (Punkte pro Stunde seit dem Post) nennen.

REDDIT — abrufbar, am 01.11. und 02.11.2026 ohne Probleme:
  a) RSS: https://www.reddit.com/r/<sub>/new.rss (neueste Posts) UND
     https://www.reddit.com/r/<sub>/top/.rss?t=day (stärkste Posts der letzten 24 h) —
     beschreibenden User-Agent setzen. HTTP 429 = Rate-Limit der geteilten IP, KEIN Block
     -> ~20-30s warten, erneut. 403 kommt nur auf /*.json und old.reddit.com.
  b) Browser: https://www.reddit.com/r/<sub>/new/ bzw. Thread-URL
     (auch https://www.reddit.com/comments/<id>/ funktioniert).
     <shreddit-post>: post-title, score, comment-count, created-timestamp, permalink.
     <shreddit-comment>: score, author, Text unter [id$="-post-rtjson-content"].
  Subs: r/artificial, r/LocalLLaMA, r/MachineLearning, r/singularity, r/OpenAI,
  r/ClaudeAI; themenbezogen weitere (z.B. r/linux, r/de, Unternehmens-Subs). Nur Posts im
  Fenster. Fällt Reddit aus: NICHTS erfinden, im Methodik-Block vermerken.

X/TWITTER — Live-Prüfung über den fxtwitter-Spiegel:
  https://api.fxtwitter.com/<user>/status/<id>
  -> created_at (UTC), Originaltext, Likes/Reposts/Antworten. So geprüfte Posts gelten
  als live verifiziert; als "über fxtwitter geprüft" kennzeichnen. Stützt sich eine Meldung
  auf einen X-Post, den Link aus der Quelle herausziehen (mit Werkzeug-Repo:
  `node tools/browser/links.js <artikel-url> 'x\.com|twitter\.com'`) und prüfen. Ohne diese
  Prüfung Reaktionen nur als Aggregator-Angabe ("laut Techmeme"). Truth Social ebenso.

BLUESKY (am 01.11. und 02.11.2026 getestet, ohne Login):
  https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=<Begriff>&sort=top&limit=50
  (optional &since=<ISO-UTC>; public.api.bsky.app liefert 403)
  Felder: createdAt, likeCount, repostCount, replyCount. createdAt selbst gegen das
  Fenster prüfen. Einzelne Posts auffrischen: app.bsky.actor.getProfile?actor=<handle>
  liefert die DID, dann app.bsky.feed.getPosts?uris=at://<DID>/app.bsky.feed.post/<rkey>
  (mit Handles statt DIDs kommt HTTP 500).

HEISE-FORUM (am 02.11.2026 getestet): Zahl der Threads, Betreffs und Texte der ersten
  Beiträge zu einem heise-Artikel als deutsches Stimmungsbarometer (mit Werkzeug-Repo:
  `node tools/browser/browse.js heise <heise-artikel-url>`). Nutzen, wenn ein Kartenthema
  einen heise-Artikel hat. Im Forum ist data-mysql-beautify-date UTC.

SOCIAL-ZAHLEN AUFFRISCHEN: Alle zitierten Zahlen (HN, Reddit, GitHub, Bluesky, X) als
  Platzhalter eintragen, damit sie höchstens 10 Minuten vor dem Versand aufgefrischt werden
  (mit Werkzeug-Repo: {hn:ID}, {rd:ID}, {gh:owner/repo}, {bs:handle/rkey}, {x:user/id};
  refresh_social.py). Zahlen ohne Platzhalter mit eigenem Stand im Methodik-Block nennen.

PRIVATSPHÄRE: Privatpersonen und ihre Handles nicht namentlich nennen, nur Organisationen,
  Medien und öffentliche Personen. Sonst beschreiben, z.B. "ein reichweitenstarker
  Security-Account".

STIMMUNGS-AMPEL: Pro Thema 🔴 überwiegend kritisch / 🟡 gemischt / 🟢 überwiegend
  positiv, mit Basis (z.B. "ca. 40 von 209 Kommentaren gelesen").

════════════════════════════════════════════════════════════════════════
DHL/P&P-RELEVANZ
════════════════════════════════════════════════════════════════════════
- In jeder Themen-Karte ein Absatz "📦 Relevanz für P&P-IT" (Einordnung, als solche
  gekennzeichnet): Was bedeutet das konkret für die IT eines großen deutschen Paket- und
  Postdienstleisters? Blickwinkel je nach Thema:
  * IT-Sicherheit: Malware, Lücken in KI-Tools, Supply-Chain, Sandboxing von Agenten
  * Entwicklungswerkzeuge und Coding-Agenten
  * Anbieter- und Cloud-Landschaft (Microsoft, SAP, AWS, Google)
  * Regulierung (EU AI Act, DSGVO, NIS2 — Post- und Kurierdienste zählen dort zu den
    erfassten Sektoren)
  * Mitbestimmung bei der Einführung von KI-Werkzeugen
  * Betrieb (Sortierung, Routenplanung, Kundenservice) und Arbeitsmarkt
  Ohne echten Bezug: das in einem Satz sagen, nichts konstruieren.
- Eigene Sektion "📦 Logistik- & DHL-Radar": frische Meldungen (gleiches Gate!) zu KI und
  IT bei DHL Group/Deutsche Post und in der Logistikbranche:
  * Wettbewerber und Postunternehmen: UPS, FedEx, Amazon Logistics, Hermes, DPD, GLS,
    La Poste, PostNL, Österreichische Post, Swiss Post
  * Technik: Sortierrobotik, autonome Zustellung, Routenoptimierung, KI im Kundenservice
  Passiert nichts das Gate: "Heute keine frische Meldung" und kurz nennen, was
  aussortiert wurde.
- DACH-Fokus: deutsche und europäische KI-Politik, Regulierung und Unternehmen gezielt
  suchen.
- Nur öffentliche Quellen. Keine Spekulation über DHL-interne Systeme, Projekte oder
  Entscheidungen; nichts formulieren, das wie eine offizielle DHL-Position klingt.

════════════════════════════════════════════════════════════════════════
AUSGEWOGENHEIT
════════════════════════════════════════════════════════════════════════
- Höchstens eine Hauptkarte pro Unternehmen. Weitere Meldungen zum selben Unternehmen in
  die Karte integrieren oder als Kurzmeldung bringen.
- Das Briefing schreibt Claude, ein Anthropic-Modell. Bei Anthropic-Themen eine kurze
  Offenlegung, nüchterne Einordnung und dieselben Maßstäbe wie bei Wettbewerbern.

════════════════════════════════════════════════════════════════════════
INTEGRITÄT (verpflichtend)
════════════════════════════════════════════════════════════════════════
- KEINE wörtlichen Zitate realer Personen — auch nicht aus live geprüften Originalen und
  auch nicht, wenn ein griffiges Zitat in vielen Artikeln identisch kursiert. Immer
  paraphrasieren und die Quelle nennen ("sinngemäß, laut <Medium>" bzw. "sinngemäß, aus
  der Original-Mail"). Kurze Fachbegriffe oder Produktnamen sind keine Zitate.
- AUTORENSCHAFT prüfen: Bei Blogs und Gastbeiträgen den tatsächlichen Autor nennen, nicht
  den Blog-Inhaber (02.11.2026: Gastbeitrag von Frank Calegari auf Terence Taos Blog).
- Social-Reaktionen als PARAPHRASE mit Quellenangabe. Stimmungsbilder nur aus tatsächlich
  abgerufenen Kommentaren. Nichts erfinden oder "rekonstruieren".
- Eigene Einordnung/Meinung ist erlaubt, aber klar als Meinung kennzeichnen.
- Zahlen (Kurse, Beträge, Prozente) nur mit Quelle und, wo sie schwanken, mit Spanne.
- BELEGSTUFE je Eintrag: ✅ Primärquelle (Unternehmen, Behörde, Studie, Repo) ·
  🟡 Sekundärquelle (Medium mit eigener Recherche oder Agentur) · 🔶 nur Aggregator
  (Google News, Techmeme). Inhalte in "Frisch" und im Radar brauchen ✅ oder 🟡;
  🔶 nur für Zeitangaben und nur gekennzeichnet.
- 🔒 an Links mit Paywall oder Zugriffssperre.
- Im Methodik-Block offenlegen: Zeitfenster (inkl. Erweiterung und Fensterende), Stand der
  Social-Zahlen, Ergebnis des Abgleichs mit den Briefings der letzten 7 Tage, Meldungen
  nach Fensterende (fürs nächste Briefing), in diesem Lauf nicht erreichbare Quellen, nur
  über Aggregatoren datierte Einträge.

════════════════════════════════════════════════════════════════════════
AUFBAU & FORMAT
════════════════════════════════════════════════════════════════════════
Reihenfolge:
  1. Kopf: Datum, Fenster (Start–Ende, deutsche Ortszeit), Stand der Social-Zahlen
  2. 📌 TL;DR-Box
  3. Offenlegung (Claude ist ein Anthropic-Modell)
  4. 🟢 Frisch: Themen-Karten, sortiert nach Relevanz für P&P-IT, bei Gleichstand nach
     Social-Resonanz
  5. 📰 Kurz notiert — Einträge ohne Social-Resonanz mit "📰 ohne Social-Echo" markieren
  6. 📦 Logistik- & DHL-Radar
  7. 🗓️ Läuft noch (max. 2, je mit Mini-Zeitleiste "TT.MM. → Ereignis")
  8. 🚫 Vom Gate aussortiert (vollständig)
  9. 🔬 Methodik (vollständig)
Themen-Karte: Titel mit 🆕 oder 🔄 · Datumszeile(n) · Fakten · 💬 Social-Puls (Zahlen,
Ampel, Basis, Punkte/h) · 📦 Relevanz für P&P-IT · 🧭 Meine Meinung.
Länge: ausführlich. NICHT kürzen.
Preheader: versteckte Vorschauzeile mit den Top-Schlagzeilen.
HTML: tabellenbasiert, Inline-CSS, Segoe UI/Arial, farbige Themen-Karten, Emoji,
TL;DR-Box, "Meine Meinung"-Callouts, Quellenlinks. Kein Flexbox/Grid, keine Remote-Bilder,
auf die das Layout angewiesen ist (Outlook). Zusätzlich:
  - <meta name="color-scheme" content="light"> und
    <meta name="supported-color-schemes" content="light"> gegen Farbverdrehung im
    Outlook-Dunkelmodus
  - <style>-Media-Query für Bildschirme unter 640 px (Tabellen auf 100 % Breite)
  - Schrift mindestens 12 px, Fließtext 14 px
Plaintext-Fallback ohne Personenzitate beilegen.
(Mit Werkzeug-Repo erzeugt tools/render_briefing.py genau dieses Format.)

════════════════════════════════════════════════════════════════════════
QA-CHECK (automatisiert, vor dem Versand)
════════════════════════════════════════════════════════════════════════
Mit Werkzeug-Repo übernimmt tools/render_briefing.py diese Prüfung (Exit-Code 2 bei
Fehlern); tools/send_brevo.py sendet nur bei bestandenem QA. Ohne Repo selbst prüfen.
Nicht senden, sondern korrigieren, wenn:
- ein Eintrag in "Frisch" oder im Radar keinen Zeitstempel im Fenster hat (vor
  Fensterbeginn oder nach Fensterende, UTC-Vergleich), keinen Quellenlink oder keine
  Belegstufe,
- ein Inhalt nur über Aggregatoren belegt ist,
- ein wörtliches Zitat einer realen Person vorkommt (auch aus live geprüften Originalen),
- "Läuft noch" mehr als 2 Einträge hat oder ein Unternehmen mehr als eine Hauptkarte,
- die Offenlegung fehlt,
- die Social-Zahlen älter als 10 Minuten sind,
- das HTML Flexbox/Grid enthält oder vom Bild abhängt,
- Betreff und Absendername nicht dieselbe Marke tragen.

════════════════════════════════════════════════════════════════════════
E-MAIL-VERSAND (Brevo API — NICHT SendGrid)
════════════════════════════════════════════════════════════════════════
- Adressen NICHT hart kodieren, sondern aus den Environment-Variablen lesen:
    Absender-Adresse : $BRIEFING_FROM        (verifiziert: cedricarnold.privat@gmail.com)
    Absender-Name    : $BRIEFING_FROM_NAME   (erwartet: "AI Social Pulse")
    Empfänger        : $BRIEFING_TO          (erwartet: cedric.arnold@deutschepost.de)
  Fehlt eine Variable, den Klammerwert als Fallback nehmen und im Abschlussbericht darauf
  hinweisen.
- Vor dem Versand Absender, Empfänger und Betreff in die Ausgabe schreiben.
- Betreff: "AI Social Pulse – Dein KI-Briefing für den <TT.MM.JJJJ>: <Top-Thema 1>,
  <Top-Thema 2>" — Top-Themen in Stichworten, insgesamt höchstens ca. 110 Zeichen.
  Absendername und Betreff tragen dieselbe Marke.
- WICHTIG — Umgebung: SMTP-Ports (25/465/587/2525) sind blockiert. Ausschließlich die
  HTTPS-API verwenden, niemals SMTP.
- Senden via POST https://api.brevo.com/v3/smtp/email
  Header:  api-key: $BREVO_API_KEY   (aus den Environment-Variablen)
           Content-Type: application/json
  Body:    {"sender": {"email": $BRIEFING_FROM, "name": $BRIEFING_FROM_NAME},
            "to": [{"email": $BRIEFING_TO}],
            "subject": "...", "htmlContent": "...", "textContent": "..."}
- HTTP 201 = akzeptiert.
- Der Key muss mit "xkeysib-" beginnen. Ein "xsmtpsib-"-Key ist ein SMTP-Key und liefert
  an dieser API 401 "Key not found".
- TRANSIENTE FEHLER: Bei 401 mit IP-Bezug, 429 oder 5xx bis zu 3x mit ~15s Abstand erneut
  versuchen. Der INHALT bleibt dabei unverändert.
- Bei dauerhaftem Fehler (z.B. 401 unauthorized, 403) den Fehler im Klartext ausgeben und
  NICHT mit erfundenem Inhalt erneut senden.
- ZUSTELLUNG VERIFIZIEREN: Message-Id aus der Antwort nehmen und über
  https://api.brevo.com/v3/smtp/statistics/events?limit=20&messageId=<urlencoded>
  auf ein "delivered"-Event prüfen. Die Events-API kann deutlich hinterherhängen
  (01.11.2026: ~60 s; 02.11.2026: ~22 min, obwohl die Mail nach 3 s zugestellt war).
  Deshalb bis zu ~30 Minuten mit Abstand prüfen, für lange Wartezeiten im Hintergrund
  (mit Werkzeug-Repo: send_brevo.py prüft bis zu 8 Minuten, danach
  `python3 -I tools/send_brevo.py --check "<Message-Id>" --wait 25 --out out/`).
- NACH HTTP 201 NIEMALS ERNEUT SENDEN, auch wenn die Events ausbleiben — das ergäbe ein
  Duplikat. Dass das Tageskontingent (GET https://api.brevo.com/v3/account) gesunken ist,
  bestätigt die Annahme. Bleibt "delivered" aus, im Abschlussbericht "angenommen
  (HTTP 201), Zustellung noch unbestätigt" melden.

════════════════════════════════════════════════════════════════════════
HINWEIS ZUR UMGEBUNG
════════════════════════════════════════════════════════════════════════
Der Container ist ephemer. Ohne eingebundenes Werkzeug-Repo existiert kein Skript aus
vorherigen Läufen: Quellen-Helfer und Versand-Skript neu bauen. Den API-Key niemals in
eine Datei schreiben, immer nur über die Environment-Variable verwenden.
Arbeitsdateien ins Scratchpad-Verzeichnis oder nach out/ im Werkzeug-Repo legen (out/ und
.runtime/ sind per .gitignore ausgeschlossen). Arbeitsdateien nie committen.

════════════════════════════════════════════════════════════════════════
ERFOLGSKRITERIUM
════════════════════════════════════════════════════════════════════════
- E-Mail mit Status 201 akzeptiert und idealerweise als "delivered" bestätigt.
- Jeder Eintrag in "Frisch" und im Radar hat einen an der Primär- oder Erstmeldung
  belegten Zeitstempel im Fenster, einen Quellenlink und eine Belegstufe.
- Die Social-Stimmung beruht auf live abgerufenen Threads mit Zahlen, Ampel und Basis.
- Jede Themen-Karte hat eine P&P-Einordnung.
- Keine erfundenen und keine wörtlichen Personenzitate.

ABSCHLUSSBERICHT an den Nutzer:
- Versandparameter, HTTP-Status, Message-Id, Zustellstatus (bei ausbleibendem Event:
  "angenommen, Zustellung unbestätigt" und wie lange geprüft wurde)
- Zeitfenster (und ob es erweitert wurde), Ergebnis des Abgleichs mit den Briefings der
  letzten 7 Tage
- die Themen mit ihren Zeitstempeln
- was das Gate aussortiert hat und warum
- alle Quellen, die in diesem Lauf nicht erreichbar waren
- ob das Werkzeug-Repo genutzt wurde, Fehler darin und sonstige Abweichungen vom Prompt
