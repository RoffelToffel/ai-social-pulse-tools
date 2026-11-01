#!/usr/bin/env python3
"""Bluesky-Suche ohne Login (getestet 01.11.2026).

  python3 -I tools/bsky.py <Begriff> [--since-unix N] [--limit 50] [--sort top|latest]

Endpunkt: https://api.bsky.app/xrpc/app.bsky.feed.searchPosts
(public.api.bsky.app liefert 403). Je Post: createdAt (UTC), Likes/Reposts/Antworten/
Zitate, Autor, Text, Web-Link. createdAt wird zusätzlich clientseitig gegen
--since-unix gefiltert, weil der Server nach "sortAt" filtert.
"""
import argparse
import datetime as dt
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

CA = "/root/.ccr/ca-bundle.crt"
UA = "AISocialPulseBriefingBot/1.0 (daily AI digest)"
BASE = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def call(params):
    req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=ssl.create_default_context(cafile=CA), timeout=30) as r:
        return json.loads(r.read())


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except (ValueError, AttributeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--since-unix", type=int)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--sort", default="top", choices=["top", "latest"])
    a = ap.parse_args()
    params = {"q": a.query, "limit": min(a.limit, 100), "sort": a.sort}
    since = dt.datetime.fromtimestamp(a.since_unix, dt.timezone.utc) if a.since_unix else None
    if since:
        params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        d = call(params)
    except urllib.error.HTTPError as e:
        if since and e.code == 400:  # Fallback ohne serverseitigen Zeitfilter
            params.pop("since")
            d = call(params)
        else:
            print(json.dumps({"ok": False, "http": e.code}))
            sys.exit(1)
    posts = []
    for p in d.get("posts", []):
        rec = p.get("record") or {}
        created = parse_iso(rec.get("createdAt", ""))
        if since and (created is None or created < since):
            continue
        handle = (p.get("author") or {}).get("handle", "")
        posts.append({
            "created_utc": created.isoformat() if created else None,
            "likes": p.get("likeCount"), "reposts": p.get("repostCount"),
            "replies": p.get("replyCount"), "quotes": p.get("quoteCount"),
            "author": handle, "text": (rec.get("text") or "")[:500],
            "url": f"https://bsky.app/profile/{handle}/post/{p.get('uri', '').rsplit('/', 1)[-1]}",
        })
    print(json.dumps({"ok": True, "query": a.query, "count": len(posts), "posts": posts},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
