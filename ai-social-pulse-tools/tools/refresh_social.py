#!/usr/bin/env python3
"""Social-Zahlen unmittelbar vor dem Versand auffrischen (getestet 01.11.2026).

  python3 -I tools/refresh_social.py --from-briefing out/briefing.json --out out/social.json

Liest alle Platzhalter aus dem Briefing-JSON und holt die aktuellen Zahlen:
  {hn:ID} {hnp:ID} {hnrate:ID}  -> Hacker News (Firebase-API: score, descendants, time)
  {rd:ID}                       -> Reddit (Browser-DOM über https://www.reddit.com/comments/<ID>/)
  {gh:owner/repo}               -> GitHub (Sterne/Forks von der Repo-Seite, Browser)
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
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BROWSER = os.path.join(ROOT, "tools", "browser")
CTX = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
PH = re.compile(r"\{(hn|hnp|hnrate|rd|gh):([^}\s]+)\}")


def hn_item(i):
    req = urllib.request.Request(f"https://hacker-news.firebaseio.com/v0/item/{i}.json",
                                 headers={"User-Agent": "AISocialPulseBriefingBot/1.0"})
    d = json.loads(urllib.request.urlopen(req, context=CTX, timeout=30).read())
    return {"score": d.get("score"), "comments": d.get("descendants"), "time": d.get("time"), "title": d.get("title")}


def node_json(script, *args, timeout=120):
    r = subprocess.run(["node", os.path.join(BROWSER, script), *args],
                       capture_output=True, text=True, timeout=timeout)
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-briefing", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    text = open(a.from_briefing, encoding="utf-8").read()
    wanted = {"hn": set(), "rd": set(), "gh": set()}
    for kind, key in PH.findall(text):
        wanted["hn" if kind.startswith("hn") else kind].add(key)

    social = {"hn": {}, "reddit": {}, "github": {}, "errors": []}
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
    social["fetched_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(social, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"hn": len(social["hn"]), "reddit": len(social["reddit"]), "github": len(social["github"]),
                      "errors": social["errors"], "fetched_utc": social["fetched_utc"]}, indent=1))
    if social["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
