#!/usr/bin/env python3
"""Fetch Nex Playground independent-site (Shopify) data without Apify.

Uses Shopify's public JSON endpoints - no API key required.

Usage: python3 fetch_shopify_site.py
"""
import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "nex_playground"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
STORE = "https://shop.nexplayground.com"

ENDPOINTS = {
    "products.json": f"{STORE}/products.json?limit=250",
    "collections.json": f"{STORE}/collections.json?limit=250",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"fetched_at": "", "products": [], "collections": []}

    data = get(ENDPOINTS["products.json"])
    (OUT / "products.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    for p in data.get("products", []):
        prices = [float(v["price"]) for v in p.get("variants", []) if v.get("price")]
        summary["products"].append({
            "id": p.get("id"),
            "title": p.get("title"),
            "handle": p.get("handle"),
            "product_type": p.get("product_type"),
            "vendor": p.get("vendor"),
            "published_at": (p.get("published_at") or "")[:10],
            "variants": len(p.get("variants", [])),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "tags": p.get("tags"),
        })

    data = get(ENDPOINTS["collections.json"])
    (OUT / "collections.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    for c in data.get("collections", []):
        summary["collections"].append({"id": c.get("id"), "title": c.get("title"),
                                       "handle": c.get("handle")})

    import datetime
    summary["fetched_at"] = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=-7))).isoformat(timespec="seconds")
    (OUT / "site_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(f"[v] products={len(summary['products'])} "
          f"collections={len(summary['collections'])} -> {OUT/'site_summary.json'}")


if __name__ == "__main__":
    main()
