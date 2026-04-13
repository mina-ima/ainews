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
    # メモリ・ハードウェア
    "memory", "hbm", "dram", "sram", "mram",
    "cpu", "processor", "intel", "amd", "arm", "risc-v", "qualcomm", "apple silicon",
    "tpu", "npu", "asic", "fpga",
    # インフラ・データセンター
    "data center", "cloud computing", "edge computing",
}

RSS_FEEDS = [
    # --- 米国主要テックメディア ---
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    # --- 学術・研究 ---
    ("arXiv AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("arXiv LG", "https://rss.arxiv.org/rss/cs.LG"),
    # --- 英国・欧州 ---
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("The Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("Reuters Tech", "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best"),
    # --- アジア・グローバル ---
    ("Nikkei Asia Tech", "https://asia.nikkei.com/rss/feed/nar?t=Technology"),
    ("South China Morning Post Tech", "https://www.scmp.com/rss/5/feed"),
    # --- 日本 ---
    ("ITmedia AI+", "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("日経クロステック", "https://xtech.nikkei.com/rss/xtech-ai.rdf"),
]

# プリント配線板（PWB/PCB）業界ニュースソース
PCB_RSS_FEEDS = [
    # --- 日本 ---
    ("JPCA", "https://www.jpca.or.jp/news/feed/"),
    # --- 海外PCB専門 ---
    ("PCB007", "https://pcb.iconnect007.com/rss"),
    ("SMT007", "https://smt.iconnect007.com/rss"),
    ("Design007", "https://design.iconnect007.com/rss"),
    # --- 電子部品・半導体 ---
    ("EE Times", "https://www.eetimes.com/feed/"),
    ("EDN", "https://www.edn.com/feed/"),
    ("Semiconductor Engineering", "https://semiengineering.com/feed/"),
    ("Electronics Weekly", "https://www.electronicsweekly.com/feed/"),
]

PCB_KEYWORDS = {
    "pcb", "pwb", "printed circuit", "printed wiring",
    "jpca", "プリント配線", "プリント基板", "実装",
    "copper clad", "銅張積層板", "フレキシブル基板", "fpc",
    "solder", "はんだ", "リフロー", "表面実装", "smt",
    "ipc", "mil規格", "rohs", "reach",
    "半導体パッケージ", "substrate", "ビルドアップ",
    "エッチング", "めっき", "ドリル", "レーザー加工",
}


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


def _is_pcb_related(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in PCB_KEYWORDS)


async def fetch_pcb_news(client: httpx.AsyncClient, limit_per_feed: int = 10) -> list[NewsItem]:
    """プリント配線板業界のニュースを取得"""
    items: list[NewsItem] = []

    for source_name, feed_url in PCB_RSS_FEEDS:
        try:
            resp = await client.get(feed_url, timeout=15.0)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                summary = entry.get("summary", "")[:300]
                if title and url:
                    # PCB専門サイトはフィルタなしで取得、汎用サイトはキーワードフィルタ
                    if source_name in ("JPCA", "PCB007") or _is_pcb_related(title, summary):
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
        hn_items, rss_items, pcb_items = await asyncio.gather(
            fetch_hackernews(client),
            fetch_rss_feeds(client),
            fetch_pcb_news(client),
        )

    # 重複URLを除去
    seen_urls: set[str] = set()
    unique: list[NewsItem] = []
    for item in hn_items + rss_items + pcb_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique.append(item)

    return unique
