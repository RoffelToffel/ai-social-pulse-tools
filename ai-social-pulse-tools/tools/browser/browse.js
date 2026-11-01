// Einzelseiten-Helfer (getestet 01.11.2026).
//   node tools/browser/browse.js text   <url> [waitMs]  -> sichtbarer Text
//   node tools/browser/browse.js html   <url> [waitMs]  -> komplettes HTML
//   node tools/browser/browse.js meta   <url> [waitMs]  -> JSON: Titel, Zeit-Metadaten, erste Absätze
//   node tools/browser/browse.js reddit <url> [waitMs]  -> JSON: <shreddit-post>/<shreddit-comment>
// Reddit-Threads lassen sich auch per https://www.reddit.com/comments/<id>/ öffnen.
'use strict';
const { launch, newContext } = require('./common');

(async () => {
  const [mode, url, waitArg] = process.argv.slice(2);
  if (!mode || !url) {
    console.error('Aufruf: browse.js text|html|meta|reddit <url> [waitMs]');
    process.exit(1);
  }
  const waitMs = parseInt(waitArg || '2500', 10);
  const browser = await launch();
  const page = await (await newContext(browser)).newPage();
  let status = null;
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    status = resp ? resp.status() : null;
    await page.waitForTimeout(waitMs);
  } catch (e) {
    console.log(JSON.stringify({ url, status, error: String(e).slice(0, 300) }));
    await browser.close();
    return;
  }
  if (mode === 'html') {
    process.stdout.write(`<!-- status ${status} -->\n` + await page.content());
  } else if (mode === 'reddit') {
    for (let i = 0; i < 4; i++) { await page.mouse.wheel(0, 3000); await page.waitForTimeout(900); }
    const data = await page.evaluate(() => ({
      posts: [...document.querySelectorAll('shreddit-post')].map(p => ({
        title: p.getAttribute('post-title'), score: p.getAttribute('score'),
        comments: p.getAttribute('comment-count'), created: p.getAttribute('created-timestamp'),
        permalink: p.getAttribute('permalink'), author: p.getAttribute('author'),
        domain: p.getAttribute('domain'), url: p.getAttribute('content-href'),
      })),
      comments: [...document.querySelectorAll('shreddit-comment')].map(c => {
        const body = c.querySelector('[id$="-post-rtjson-content"]');
        return { score: c.getAttribute('score'), author: c.getAttribute('author'),
                 depth: c.getAttribute('depth'), created: c.getAttribute('created'),
                 text: body ? body.innerText.trim().slice(0, 700) : '' };
      }),
    }));
    console.log(JSON.stringify({ status, url, final: page.url(), ...data }, null, 1));
  } else if (mode === 'meta') {
    const data = await page.evaluate(() => {
      const metas = {};
      document.querySelectorAll('meta[property], meta[name], meta[itemprop]').forEach(m => {
        const k = m.getAttribute('property') || m.getAttribute('name') || m.getAttribute('itemprop');
        if (/time|date|publish|modified|title|author|description|byl/i.test(k)) metas[k] = m.getAttribute('content');
      });
      const times = [...document.querySelectorAll('time')].slice(0, 6)
        .map(t => ({ dt: t.getAttribute('datetime'), txt: t.innerText.trim().slice(0, 80) }));
      const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent.slice(0, 2500));
      const paras = [...document.querySelectorAll('article p, main p, p')].map(p => p.innerText.trim())
        .filter(t => t.length > 60).slice(0, 14);
      return { title: document.title, metas, times, ld, paras };
    });
    console.log(JSON.stringify({ status, url, final: page.url(), ...data }, null, 1));
  } else {
    const txt = await page.evaluate(() => (document.body ? document.body.innerText : ''));
    process.stdout.write(`[status ${status}] ${url}\n` + txt);
  }
  await browser.close();
})();
