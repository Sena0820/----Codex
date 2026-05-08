from __future__ import annotations

import json
import logging
import re
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any

import feedparser
import requests
import yaml
from dateutil import parser as date_parser


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "sources.yaml"
OUTPUT_DIR = BASE_DIR / "data" / "raw"
TIMEOUT_SECONDS = 20
MAX_SUMMARY_LENGTH = 500


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def load_config(config_path: Path) -> dict[str, list[dict[str, Any]]]:
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    topics = config.get("topics", [])
    sources = config.get("sources", [])

    valid_topics: list[dict[str, Any]] = []
    for topic in topics:
        if not topic.get("name") or not topic.get("keywords"):
            logging.warning("Skipping invalid topic config: %s", topic)
            continue
        valid_topics.append(topic)

    valid_sources: list[dict[str, Any]] = []
    for source in sources:
        if not all(key in source for key in ("name", "category", "url")):
            logging.warning("Skipping invalid source config: %s", source)
            continue
        valid_sources.append(source)

    return {"topics": valid_topics, "sources": valid_sources}


def parse_published(entry: Any) -> str:
    candidates = [
        entry.get("published"),
        entry.get("updated"),
        entry.get("created"),
    ]

    for value in candidates:
        if not value:
            continue
        try:
            return date_parser.parse(value).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            continue

    return ""


def strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_summary(entry: Any) -> str:
    candidates = [
        entry.get("summary"),
        entry.get("description"),
    ]

    if entry.get("content"):
        for content_block in entry.get("content", []):
            candidates.append(content_block.get("value"))

    for value in candidates:
        text = strip_html(value or "")
        if text:
            return text[:MAX_SUMMARY_LENGTH]

    return ""


def match_topics(text: str, topics: list[dict[str, Any]]) -> list[str]:
    haystack = text.casefold()
    matched_topics: list[str] = []

    for topic in topics:
        keywords = topic.get("keywords", [])
        if any(keyword.casefold() in haystack for keyword in keywords):
            matched_topics.append(topic["name"])

    return matched_topics


def fetch_feed(source: dict[str, Any], topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logging.info("Fetching %s", source["name"])

    response = requests.get(
        source["url"],
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "daily-info-dashboard/0.2"},
    )
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Failed to parse feed: {source['url']}")

    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        url = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        summary = extract_summary(entry)

        if not url or not title:
            continue

        matched_topics = match_topics(f"{title}\n{summary}", topics)
        if not matched_topics:
            continue

        items.append(
            {
                "title": title,
                "url": url,
                "published_at": parse_published(entry),
                "source_name": source["name"],
                "source_category": source["category"],
                "summary": summary,
                "matched_topics": matched_topics,
            }
        )

    return items


def deduplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    unique_items: list[dict[str, Any]] = []

    for item in items:
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique_items.append(item)

    return unique_items


def save_items(
    items: list[dict[str, Any]],
    output_dir: Path,
    topics: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date.today().isoformat()}.json"

    payload = {
        "generated_at": date.today().isoformat(),
        "topics": topics,
        "sources": sources,
        "item_count": len(items),
        "items": items,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return output_path


def main() -> None:
    config = load_config(CONFIG_PATH)
    topics = config["topics"]
    sources = config["sources"]
    collected_items: list[dict[str, Any]] = []

    for source in sources:
        try:
            collected_items.extend(fetch_feed(source, topics))
        except (requests.RequestException, ValueError) as error:
            logging.warning("Skipping %s: %s", source["name"], error)

    unique_items = deduplicate_items(collected_items)
    saved_path = save_items(unique_items, OUTPUT_DIR, topics, sources)

    logging.info("Saved %s matched items to %s", len(unique_items), saved_path)


if __name__ == "__main__":
    main()

