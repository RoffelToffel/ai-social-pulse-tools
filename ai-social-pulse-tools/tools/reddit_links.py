#!/usr/bin/env python3
"""Externe Links aus Reddit-Atom-Einträgen (getestet 01.11.2026).

  python3 -I tools/reddit_links.py "https://www.reddit.com/r/<sub>/new.rss?limit=100" <post_id> [<post_id> ...]
"""
import ssl, sys, time, urllib.request, xml.etree.ElementTree as ET
from html.parser import HTMLParser
CA="/root/.ccr/ca-bundle.crt"; UA="AISocialPulseBriefingBot/1.0 (daily AI digest)"
NS={"a":"http://www.w3.org/2005/Atom"}
class A(HTMLParser):
    def __init__(s): super().__init__(); s.l=[]
    def handle_starttag(s,t,a):
        if t=="a":
            h=dict(a).get("href","")
            if h and "reddit.com" not in h and "redd.it" not in h: s.l.append(h)
ids=set(sys.argv[2:])
req=urllib.request.Request(sys.argv[1],headers={"User-Agent":UA})
for attempt in range(3):
    try:
        raw=urllib.request.urlopen(req,context=ssl.create_default_context(cafile=CA),timeout=30).read(); break
    except Exception as e:
        print("retry",e); time.sleep(25)
root=ET.fromstring(raw)
for e in root.findall("a:entry",NS):
    link=e.find("a:link",NS).get("href")
    if not any(i in link for i in ids): continue
    p=A(); p.feed("".join(e.find("a:content",NS).itertext()))
    print("".join(e.find("a:title",NS).itertext())[:90]); print("   ",link); [print("    ->",x) for x in dict.fromkeys(p.l)]
