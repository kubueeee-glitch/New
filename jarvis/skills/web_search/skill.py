from __future__ import annotations

import json
import urllib.parse
import urllib.request


def run(args: dict, ctx) -> str:
    query = (args.get("query") or args.get("text") or "").strip()
    if not query:
        return "Nie usłyszałem, czego mam poszukać."
    url = (
        "https://api.duckduckgo.com/?format=json&no_html=1&q="
        + urllib.parse.quote(query)
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return "Wyszukiwarka nie odpowiada."
    answer = (data.get("AbstractText") or data.get("Answer") or "").strip()
    if not answer:
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                answer = topic["Text"]
                break
    return answer[:300] if answer else "Nic sensownego nie znalazłem."
