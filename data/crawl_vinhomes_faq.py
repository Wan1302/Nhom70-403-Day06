#!/usr/bin/env python3
import argparse
import csv
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://market.vinhomes.vn/api/faq/questions"


def strip_html(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_iso_time(ms: Optional[int]) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def fetch_page(
    page: int,
    size: int,
    category_ids: Optional[int] = None,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"page": page, "size": size}
    if category_ids is not None:
        params["category_ids"] = category_ids
    if keyword:
        params["keyword"] = keyword

    url = f"{API_URL}?{urlencode(params)}"
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["data"]


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    category_info = item.get("category_info") or {}
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "alias": item.get("alias"),
        "category_id": item.get("category_id"),
        "category_title": category_info.get("title"),
        "detail_url": item.get("detail_url"),
        "content_html": item.get("content", ""),
        "content_text": strip_html(item.get("content", "")),
        "publish_time_iso": to_iso_time(item.get("publish_time")),
        "updated_time_iso": to_iso_time(item.get("updated_time")),
        "raw": item,
    }


def crawl_all(
    size: int,
    category_ids: Optional[int] = None,
    keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    page = 1
    total = None
    collected: List[Dict[str, Any]] = []
    seen_ids = set()

    while True:
        data = fetch_page(page=page, size=size, category_ids=category_ids, keyword=keyword)
        rows = data.get("data", [])
        total = data.get("total", total)

        if not rows:
            break

        for row in rows:
            faq_id = row.get("id")
            if faq_id in seen_ids:
                continue
            seen_ids.add(faq_id)
            collected.append(normalize_item(row))

        print(f"Fetched page {page}: +{len(rows)} items (collected={len(collected)}/{total})")

        if total is not None and len(collected) >= total:
            break
        page += 1

    return collected


def save_json(items: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def save_csv(items: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "title",
        "alias",
        "category_id",
        "category_title",
        "detail_url",
        "content_text",
        "publish_time_iso",
        "updated_time_iso",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl FAQ từ market.vinhomes.vn")
    parser.add_argument("--size", type=int, default=100, help="Số bản ghi mỗi trang")
    parser.add_argument("--category-ids", type=int, default=None, help="Lọc theo category_id")
    parser.add_argument("--keyword", type=str, default=None, help="Từ khóa tìm kiếm")
    parser.add_argument("--json-out", type=Path, default=Path("output/vinhomes_faq.json"))
    parser.add_argument("--csv-out", type=Path, default=Path("output/vinhomes_faq.csv"))
    args = parser.parse_args()

    items = crawl_all(size=args.size, category_ids=args.category_ids, keyword=args.keyword)
    save_json(items, args.json_out)
    save_csv(items, args.csv_out)
    print(f"Done. Saved {len(items)} FAQs")
    print(f"JSON: {args.json_out}")
    print(f"CSV:  {args.csv_out}")


if __name__ == "__main__":
    main()
