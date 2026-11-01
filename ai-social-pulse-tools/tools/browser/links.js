// Links einer Seite nach Regex filtern, z.B. um die Primärquelle hinter einem Bericht zu finden
// (getestet 01.11.2026).
//   node tools/browser/links.js <url> "<regex>"
//   Beispiel: node tools/browser/links.js https://the-decoder.com/... "anthropic\\.com|arxiv"
'use strict';
const { launch, newContext } = require('./common');

(async () => {
  const [url, re] = process.argv.slice(2);
  if (!url) { console.error('Aufruf: links.js <url> "<regex>"'); process.exit(1); }
  const browser = await launch();
  const page = await (await newContext(browser)).newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
  await page.waitForTimeout(2500);
  const links = await page.evaluate((pattern) => [...document.querySelectorAll('a[href]')]
    .map(a => a.href).filter(h => new RegExp(pattern || '.').test(h)), re);
  console.log([...new Set(links)].join('\n'));
  await browser.close();
})();
