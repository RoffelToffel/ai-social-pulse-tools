// Batch-Verifikation von Artikeln (getestet 01.11.2026):
// je URL finale URL, HTTP-Status, Titel, Zeit-Metadaten (meta, <time>, JSON-LD) und erste Absätze
// (Rückfall auf Textzeilen, wenn eine Seite kaum <p>-Absätze hat; Feld parasSource).
// Google-News-Links (news.google.com/rss/articles/...) werden per JS-Redirect aufgelöst.
//   node tools/browser/batchmeta.js urls.txt out/verify.json [parallel=3] [absätze=6]
'use strict';
const fs = require('fs');
const { launch, newContext } = require('./common');

async function one(ctx, url, nParas) {
  const page = await ctx.newPage();
  const res = { url };
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
    res.status = resp ? resp.status() : null;
    if (url.includes('news.google.com')) {
      for (let i = 0; i < 20 && page.url().includes('news.google.com'); i++) await page.waitForTimeout(500);
    }
    await page.waitForTimeout(2500);
    res.final = page.url();
    Object.assign(res, await page.evaluate((n) => {
      const metas = {};
      document.querySelectorAll('meta[property], meta[name], meta[itemprop]').forEach(m => {
        const k = m.getAttribute('property') || m.getAttribute('name') || m.getAttribute('itemprop');
        if (/publish|modified|date|time|author|byl|parsely-pub/i.test(k)) metas[k] = (m.getAttribute('content') || '').slice(0, 200);
      });
      const times = [...document.querySelectorAll('time')].slice(0, 5)
        .map(t => ({ dt: t.getAttribute('datetime'), txt: t.innerText.trim().slice(0, 60) }));
      const ldDates = [];
      document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
        const m = s.textContent.match(/"date(Published|Created|Modified)"\s*:\s*"[^"]+"/g);
        if (m) ldDates.push(...m.slice(0, 4));
      });
      const h1 = (document.querySelector('h1') || {}).innerText || '';
      const pickParas = () => {
        // Absätze aus dem Artikel-Container; <p> nur, wenn sie den Großteil seines Textes abdecken
        // (Phoronix u.a. setzen den Artikel ohne <p>, Boilerplate steht dagegen in <p>).
        const sels = ['article', '[itemprop="articleBody"]', '.article-body', '.entry-content', '.post-content',
          '.article-content', '[class*="article-details"]', 'main', '#content', '.content'];
        const cont = sels.map(s => document.querySelector(s)).find(Boolean);
        const pOf = el => [...new Set([...el.querySelectorAll('p')].map(p => p.innerText.trim()).filter(t => t.length > 50))];
        const linesOf = el => [...new Set(el.innerText.split('\n').map(t => t.trim()).filter(t => t.length > 80))];
        const len = a => a.reduce((n, t) => n + t.length, 0);
        if (cont) {
          const ps = pOf(cont), ls = linesOf(cont);
          if (ps.length >= 3 && len(ps) >= 0.6 * len(ls)) return [ps, 'p:container'];
          if (ls.length >= 3) return [ls, 'text:container'];
        }
        const ps = pOf(document.body);
        return ps.length >= 3 ? [ps, 'p:body'] : [linesOf(document.body), 'text:body'];
      };
      const [allParas, parasSource] = pickParas();
      return { title: document.title.slice(0, 200), h1: h1.slice(0, 200), metas, times, ldDates,
               paras: allParas.slice(0, n), parasSource };
    }, nParas));
  } catch (e) {
    res.error = String(e).slice(0, 200);
    try { res.final = page.url(); } catch (_) { /* ignore */ }
  }
  await page.close();
  return res;
}

(async () => {
  const [listFile, outFile, concArg, parasArg] = process.argv.slice(2);
  if (!listFile || !outFile) { console.error('Aufruf: batchmeta.js urls.txt out.json [parallel] [absätze]'); process.exit(1); }
  const urls = fs.readFileSync(listFile, 'utf8').split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('#'));
  const conc = parseInt(concArg || '3', 10);
  const nParas = parseInt(parasArg || '6', 10);
  const browser = await launch();
  const ctx = await newContext(browser);
  const out = new Array(urls.length);
  let idx = 0;
  async function worker() {
    while (idx < urls.length) {
      const i = idx++;
      out[i] = await one(ctx, urls[i], nParas);
      process.stderr.write(`[${i + 1}/${urls.length}] ${out[i].status || out[i].error || ''} ${urls[i].slice(0, 90)}\n`);
    }
  }
  await Promise.all(Array.from({ length: conc }, worker));
  fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
  await browser.close();
})();
