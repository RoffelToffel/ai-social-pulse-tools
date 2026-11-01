// GitHub-Zeitstempel und Kennzahlen über die Webseite (getestet 01.11.2026).
// GitHub-API und Atom-Feeds sind per Proxy-Policy gesperrt, die Webseiten funktionieren.
//   node tools/browser/gh_commits.js https://github.com/<owner>/<repo>[/commits/<branch>] [...]
// Ausgabe: JSON-Liste mit relative-time[datetime]-Werten (UTC), Commit-Titeln, Sternen, Forks.
'use strict';
const { launch, newContext } = require('./common');

(async () => {
  const urls = process.argv.slice(2);
  if (!urls.length) { console.error('Aufruf: gh_commits.js <github-url> [...]'); process.exit(1); }
  const browser = await launch();
  const ctx = await newContext(browser);
  const results = [];
  for (const url of urls) {
    const page = await ctx.newPage();
    const res = { url };
    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
      res.status = resp ? resp.status() : null;
      await page.waitForTimeout(3500);
      Object.assign(res, await page.evaluate(() => {
        const text = document.body ? document.body.innerText : '';
        const star = text.match(/Star\s*([\d.,]+k?)/);
        const fork = text.match(/Fork\s*([\d.,]+k?)/);
        return {
          commit_times_utc: [...new Set([...document.querySelectorAll('relative-time')]
            .map(e => e.getAttribute('datetime')).filter(Boolean))].slice(0, 15),
          titles: [...document.querySelectorAll('[data-testid="commit-row-item"] h4, .markdown-title')]
            .map(e => e.innerText.trim().slice(0, 100)).slice(0, 15),
          stars: star ? star[1] : null,
          forks: fork ? fork[1] : null,
        };
      }));
    } catch (e) {
      res.error = String(e).slice(0, 200);
    }
    results.push(res);
    await page.close();
  }
  console.log(JSON.stringify(results, null, 1));
  await browser.close();
})();
