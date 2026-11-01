// Gemeinsamer Browser-Start für alle Playwright-Helfer (getestet 01.11.2026).
// Vertraut gezielt NUR der Agent-Proxy-CA (SPKI-Pin aus setup.sh) –
// niemals --ignore-certificate-errors, niemals HTTPS_PROXY entfernen.
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const RUNTIME = path.join(ROOT, '.runtime');
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36';

function readRuntime(name) {
  try { return fs.readFileSync(path.join(RUNTIME, name), 'utf8').trim(); } catch (e) { return ''; }
}

function chromePath() {
  const p = readRuntime('chrome_path');
  if (p && fs.existsSync(p)) return p;
  try {
    return execSync('find /opt/pw-browsers -maxdepth 3 -name chrome -type f 2>/dev/null | head -1')
      .toString().trim() || undefined;
  } catch (e) { return undefined; }
}

function spkiPin() {
  const s = readRuntime('spki.txt');
  if (s) return s;
  return execSync('openssl x509 -in /root/.ccr/agent-proxy-ca.crt -pubkey -noout | openssl pkey -pubin -outform der'
    + ' | openssl dgst -sha256 -binary | openssl enc -base64').toString().trim();
}

async function launch() {
  const { chromium } = require('playwright');
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  return chromium.launch({
    executablePath: chromePath(),
    args: ['--no-sandbox', `--ignore-certificate-errors-spki-list=${spkiPin()}`],
    proxy: proxy ? { server: proxy } : undefined,
  });
}

function newContext(browser, extra = {}) {
  return browser.newContext({ userAgent: UA, locale: 'en-US', viewport: { width: 1280, height: 1800 }, ...extra });
}

module.exports = { launch, newContext, UA, ROOT };
