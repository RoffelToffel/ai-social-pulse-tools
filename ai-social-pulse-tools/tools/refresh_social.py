#!/usr/bin/env python3
"""Social-Zahlen unmittelbar vor dem Versand auffrischen (getestet 01.11. und 02.11.2026).

  python3 -I tools/refresh_social.py --from-briefing out/briefing.json --out out/social.json

Liest alle Platzhalter aus dem Briefing-JSON und holt die aktuellen Zahlen:
  {hn:ID} {hnp:ID} {hnrate:ID}  -> Hacker News (Firebase-API: score, descendants, time)
  {rd:ID}                       -> Reddit (Browser-DOM über https://www.reddit.com/comments/<ID>/)
  {gh:owner/repo}               -> GitHub (Sterne/Forks von der Repo-Seite, Browser)
  {bs:handle/rkey}              -> Bluesky (getProfile -> DID, dann getPosts; mit Handles in
                                   at://-URIs liefert getPosts HTTP 500)
  {x:user/statusid}             -> X/Twitter über den fxtwitter-Spiegel (Likes, Reposts, Antworten)
render_briefing.py verlangt, dass social.json höchstens 10 Minuten alt ist.
"""
import argparse
import datetime as dt
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BROWSER = os.path.join(ROOT, "tools", "browser")
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
UA = {"User-Agent": "AISocialPulseBriefingBot/1.0 (daily AI digest)"}
PH = re.compile(r"\{(hn|hnp|hnrate|rd|gh|bs|x):([^}\s]+)\}")
BSKY = "https://api.bsky.app/xrpc/"


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return json.loads(r.read())


def hn_item(i):
    d = get_json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
    return {"score": d.get("score"), "comments": d.get("descendants"), "time": d.get("time"), "title": d.get("title")}


def node_json(script, *args, timeout=120):
    r = subprocess.run(["node", os.path.join(BROWSER, script), *args],
                       capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout)


def bluesky_posts(keys, errors):
    """keys: {'handle/rkey', ...} -> {key: {...}}"""
    dids, uris = {}, {}
    for key in sorted(keys):
        handle, _, rkey = key.partition("/")
        if not rkey:
            errors.append(f"bluesky {key}: Format handle/rkey erwartet")
            continue
        try:
            if handle not in dids:
                dids[handle] = get_json(BSKY + "app.bsky.actor.getProfile?actor=" + urllib.parse.quote(handle))["did"]
            uris[f"at://{dids[handle]}/app.bsky.feed.post/{rkey}"] = key
        except Exception as e:
            errors.append(f"bluesky {key}: {e}")
    out, items = {}, list(uris.items())
    for i in range(0, len(items), 25):  # getPosts nimmt höchstens 25 URIs
        q = "&".join("uris=" + urllib.parse.quote(u, safe="") for u, _ in items[i:i + 25])
        try:
            for p in get_json(BSKY + "app.bsky.feed.getPosts?" + q).get("posts", []):
                key = uris.get(p.get("uri"))
                if key:
                    out[key] = {"likes": p.get("likeCount"), "reposts": p.get("repostCount"),
                                "replies": p.get("replyCount"), "quotes": p.get("quoteCount"),
                                "created": (p.get("record") or {}).get("createdAt")}
        except Exception as e:
            errors.append(f"bluesky getPosts: {e}")
    for key in uris.values():
        if key not in out:
            errors.append(f"bluesky {key}: Post nicht gefunden")
    return out


def x_post(key):
    user, _, sid = key.partition("/")
    t = get_json(f"https://api.fxtwitter.com/{user}/status/{sid}").get("tweet") or {}
    if not t:
        raise ValueError("fxtwitter lieferte keinen Post")
    ts = t.get("created_timestamp")
    return {"likes": t.get("likes"), "reposts": t.get("retweets"), "replies": t.get("replies"),
            "created_utc": dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat() if ts else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-briefing", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    text = open(a.from_briefing, encoding="utf-8").read()
    wanted = {"hn": set(), "rd": set(), "gh": set(), "bs": set(), "x": set()}
    for kind, key in PH.findall(text):
        wanted["hn" if kind.startswith("hn") else kind].add(key)

    social = {"hn": {}, "reddit": {}, "github": {}, "bluesky": {}, "x": {}, "errors": []}
    for i in sorted(wanted["hn"]):
        try:
            social["hn"][i] = hn_item(i)
        except Exception as e:
            social["errors"].append(f"hn {i}: {e}")
    for pid in sorted(wanted["rd"]):
        try:
            d = node_json("browse.js", "reddit", f"https://www.reddit.com/comments/{pid}/", "2500")
            p = d["posts"][0]
            social["reddit"][pid] = {"score": p["score"], "comments": p["comments"],
                                     "created": p["created"], "permalink": p.get("permalink")}
        except Exception as e:
            social["errors"].append(f"reddit {pid}: {e}")
    for repo in sorted(wanted["gh"]):
        try:
            d = node_json("gh_commits.js", f"https://github.com/{repo}")[0]
            social["github"][repo] = {"stars": d.get("stars"), "forks": d.get("forks")}
        except Exception as e:
            social["errors"].append(f"github {repo}: {e}")
    if wanted["bs"]:
        social["bluesky"] = bluesky_posts(wanted["bs"], social["errors"])
    for key in sorted(wanted["x"]):
        try:
            social["x"][key] = x_post(key)
        except Exception as e:
            social["errors"].append(f"x {key}: {e}")
    social["fetched_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(social, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: len(social[k]) for k in ("hn", "reddit", "github", "bluesky", "x")}
                     | {"errors": social["errors"], "fetched_utc": social["fetched_utc"]}, indent=1))
    if social["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
