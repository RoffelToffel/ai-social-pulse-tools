// Einzelseiten-Helfer (getestet 01.11.2026).
//   node tools/browser/browse.js text   <url> [waitMs]  -> sichtbarer Text
//   node tools/browser/browse.js html   <url> [waitMs]  -> komplettes HTML
//   node tools/browser/browse.js meta   <url> [waitMs]  -> JSON: Titel, Zeit-Metadaten, erste Absätze
//   node tools/browser/browse.js reddit <url> [waitMs]  -> JSON: <shreddit-post>/<shreddit-comment>
//   node tools/browser/browse.js heise  <heise-artikel-url> [waitMs] [maxBeiträge=8]
//        -> JSON: Forum-Link, Zahl der Threads, Threads (Zeit UTC, Betreff, Link) und Texte der
//           ersten Beiträge. Autorennamen werden bewusst nicht ausgegeben.
// Reddit-Threads lassen sich auch per https://www.reddit.com/comments/<id>/ öffnen.
'use strict';
const { launch, newContext } = require('./common');

(async () => {
  const [mode, url, waitArg, maxArg] = process.argv.slice(2);
  if (!mode || !url) {
    console.error('Aufruf: browse.js text|html|meta|reddit|heise <url> [waitMs] [maxBeiträge]');
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
  } else if (mode === 'heise') {
    // 1) Forum-Link im Artikel finden (Link „Kommentar lesen“), 2) Thread-Liste parsen,
    // 3) die ersten Beiträge öffnen. data-mysql-beautify-date ist UTC (title = Ortszeit).
    const maxPosts = parseInt(maxArg || '8', 10);
    const forum = await page.evaluate(() => {
      const a = [...document.querySelectorAll('a[href*="/forum/heise-online/Kommentare/"]')][0];
      return a ? a.href : null;
    });
    const out = { status, url, forum, threads: [], thread_count: 0, posts: [] };
    if (forum) {
      await page.goto(forum, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(waitMs);
      out.threads = await page.evaluate(() => [...document.querySelectorAll('#tree_thread_list > li.posting_element')]
        .map(li => {
          const t = li.querySelector('time');
          const a = li.querySelector('a.posting_subject');
          return { time_utc: t ? t.getAttribute('data-mysql-beautify-date') : null,
                   time_local: t ? t.getAttribute('title') : null,
                   subject: a ? a.innerText.trim() : '', url: a ? a.href : null,
                   has_replies: !li.classList.contains('no_subthread') };
        }));
      out.thread_count = out.threads.length;
      for (const th of out.threads.slice(0, maxPosts)) {
        if (!th.url) continue;
        try {
          await page.goto(th.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
          await page.waitForTimeout(1200);
          const text = await page.evaluate(() => {
            const b = document.querySelector('div.post .body_format_indicator') || document.querySelector('div.post');
            return b ? b.innerText.trim().slice(0, 900) : '';
          });
          out.posts.push({ subject: th.subject, time_utc: th.time_utc, url: th.url, text });
        } catch (e) {
          out.posts.push({ subject: th.subject, url: th.url, error: String(e).slice(0, 120) });
        }
      }
    }
    console.log(JSON.stringify(out, null, 1));
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
      return { title: document.title, metas, times, ld, paras: allParas.slice(0, 14), parasSource };
    });
    console.log(JSON.stringify({ status, url, final: page.url(), ...data }, null, 1));
  } else {
    const txt = await page.evaluate(() => (document.body ? document.body.innerText : ''));
    process.stdout.write(`[status ${status}] ${url}\n` + txt);
  }
  await browser.close();
})();
