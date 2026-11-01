#!/usr/bin/env bash
# Einmal pro Lauf ausführen (getestet 01.11.2026):
#  - prüft das vorinstallierte Playwright (NICHT neu installieren, kein `playwright install`)
#  - ermittelt den Chromium-Pfad unter /opt/pw-browsers
#  - berechnet den SPKI-Pin der Agent-Proxy-CA (Chromium vertraut gezielt nur dieser CA)
#  - zeigt Proxy-Status und JETZT
# Ergebnisse landen in .runtime/ (nicht versioniert). Arbeitsdateien gehören nach out/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RT="$ROOT/.runtime"
mkdir -p "$RT" "$ROOT/out"

if node -e "require('playwright')" 2>/dev/null; then
  echo "Playwright: global vorhanden ($(node -e "console.log(require('playwright/package.json').version)"))"
else
  echo "Playwright fehlt global -> Installation ohne Browser-Download nach $RT"
  (cd "$RT" && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install playwright --no-audit --no-fund >/dev/null)
  echo "export NODE_PATH=$RT/node_modules" > "$RT/env.sh"
  echo "Hinweis: vor Node-Aufrufen 'source $RT/env.sh' ausführen."
fi

CHROME="$(find /opt/pw-browsers -maxdepth 3 -name chrome -type f 2>/dev/null | head -1 || true)"
if [ -n "$CHROME" ]; then
  echo "$CHROME" > "$RT/chrome_path"
  echo "Chromium: $CHROME"
else
  echo "WARNUNG: kein Chromium unter /opt/pw-browsers gefunden"
fi

openssl x509 -in /root/.ccr/agent-proxy-ca.crt -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary | openssl enc -base64 > "$RT/spki.txt"
echo "SPKI-Pin der Proxy-CA: $(cat "$RT/spki.txt")"

if [ -n "${HTTPS_PROXY:-}" ]; then
  curl -sS "$HTTPS_PROXY/__agentproxy/status" 2>/dev/null \
    | python3 -I -c "import json,sys; d=json.load(sys.stdin); print('Proxy recentRelayFailures:', d.get('recentRelayFailures'))" \
    || echo "Proxy-Status nicht abrufbar"
fi

echo "JETZT: $(date -u '+%Y-%m-%d %H:%M:%S UTC') | unix $(date -u +%s) | Berlin: $(TZ=Europe/Berlin date '+%d.%m.%Y %H:%M %Z')"
for v in BRIEFING_FROM BRIEFING_FROM_NAME BRIEFING_TO; do
  if [ -n "${!v:-}" ]; then echo "$v gesetzt"; else echo "$v FEHLT -> Fallback aus config/defaults.json"; fi
done
if [ -n "${BREVO_API_KEY:-}" ]; then echo "BREVO_API_KEY gesetzt (Präfix ${BREVO_API_KEY:0:8})"; else echo "BREVO_API_KEY FEHLT"; fi
