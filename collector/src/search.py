"""Hacker News API + RSS フィードからAI・テクノロジーニュースを収集"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import feedparser
import httpx

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

AI_KEYWORDS = {
    "ai", "artificial intelligence", "llm", "gpt", "claude", "gemini",
    "machine learning", "deep learning", "neural", "transformer",
    "openai", "anthropic", "google deepmind", "meta ai", "mistral",
    "nvidia", "gpu", "chip", "semiconductor",
    "robot", "autonomous", "self-driving",
    "copilot", "cursor", "coding assistant",
    "diffusion", "stable diffusion", "midjourney", "dall-e",
    "rag", "fine-tuning", "embedding", "vector",
    "agent", "mcp", "tool use",
}

RSS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Ars Technica AI", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
]


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    summary: str = ""


def _is_ai_related(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in AI_KEYWORDS)


async def fetch_hackernews(client: httpx.AsyncClient, limit: int = 30) -> list[NewsItem]:
    """Hacker News トップストーリーからAI関連記事を取得"""
    resp = await client.get(HN_TOP_URL)
    story_ids = resp.json()[:200]

    items: list[NewsItem] = []
    tasks = [client.get(HN_ITEM_URL.format(sid)) for sid in story_ids[:80]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            continue
        story = r.json()
        if not story or story.get("type") != "story":
            continue
        title = story.get("title", "")
        url = story.get("url", f"https://news.ycombinator.com/item?id={story['id']}")
        if _is_ai_related(title):
            items.append(NewsItem(title=title, url=url, source="Hacker News"))
        if len(items) >= limit:
            break

    return items


async def fetch_rss_feeds(client: httpx.AsyncClient, limit_per_feed: int = 5) -> list[NewsItem]:
    """RSSフィードからニュース取得"""
    items: list[NewsItem] = []

    for source_name, feed_url in RSS_FEEDS:
        try:
            resp = await client.get(feed_url, timeout=15.0)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                summary = entry.get("summary", "")[:300]
                if title and url:
                    items.append(NewsItem(
                        title=title,
                        url=url,
                        source=source_name,
                        summary=summary,
                    ))
        except Exception:
            continue

    return items


async def collect_news() -> list[NewsItem]:
    """全ソースからニュースを収集して統合"""
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "ainews-collector/1.0"},
        follow_redirects=True,
    ) as client:
        hn_items, rss_items = await asyncio.gather(
            fetch_hackernews(client),
            fetch_rss_feeds(client),
        )

    # 重複URLを除去
    seen_urls: set[str] = set()
    unique: list[NewsItem] = []
    for item in hn_items + rss_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique.append(item)

    return unique
