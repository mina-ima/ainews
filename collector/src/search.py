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

# HNから広くテクノロジー記事を拾うためのキーワード（AI以外）
TECH_KEYWORDS = {
    # 製造・エンジニアリング
    "3d print", "additive manufacturing", "cnc", "laser", "manufacturing",
    "factory", "automation", "industrial", "assembly",
    # エレクトロニクス
    "pcb", "circuit board", "electronics", "sensor", "battery", "ev",
    "power supply", "motor", "actuator", "mems", "iot",
    # 材料・化学
    "graphene", "carbon fiber", "metamaterial", "superconductor", "polymer",
    "ceramic", "composite", "alloy", "nanomaterial",
    # エネルギー・環境
    "solar", "wind energy", "hydrogen", "fuel cell", "nuclear fusion",
    "renewable", "carbon capture", "sustainability",
    # 通信・ネットワーク
    "5g", "6g", "satellite", "starlink", "fiber optic", "quantum network",
    # 宇宙・航空
    "spacex", "nasa", "rocket", "satellite", "aerospace", "drone",
    # バイオ・医療
    "biotech", "crispr", "gene therapy", "prosthetic", "medical device",
    # ロボティクス・メカトロニクス
    "humanoid", "exoskeleton", "robotic arm", "lidar", "computer vision",
    # 量子
    "quantum computing", "qubit", "quantum",
    # その他先端技術
    "breakthrough", "patent", "prototype", "innovation", "open source hardware",
}

RSS_FEEDS = [
    # --- 米国主要テックメディア（AI特化→汎用フィードに拡張） ---
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("TechCrunch Hardware", "https://techcrunch.com/category/hardware/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("The Verge Tech", "https://www.theverge.com/rss/tech/index.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss"),
    ("New Atlas", "https://newatlas.com/index.rss"),
    ("Hackaday", "https://hackaday.com/feed/"),
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
    # --- 日本（幅広く） ---
    ("ITmedia AI+", "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("ITmedia NEWS", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
    ("日経クロステック", "https://xtech.nikkei.com/rss/xtech-ai.rdf"),
    ("日経クロステック 電子・機械", "https://xtech.nikkei.com/rss/xtech-mono.rdf"),
    ("EE Times Japan", "https://eetimes.itmedia.co.jp/ee/rss/020.xml"),
    ("MONOist", "https://monoist.itmedia.co.jp/mn/rss/020.xml"),
    # --- 製造業・エンジニアリング ---
    ("Manufacturing.net", "https://www.manufacturing.net/rss.xml"),
    ("Engineering.com", "https://www.engineering.com/feed/"),
    ("3D Printing Industry", "https://3dprintingindustry.com/feed/"),
]

# プリント配線板（PWB/PCB）・電子実装・製造業界ニュースソース
PCB_RSS_FEEDS = [
    # --- 日本 ---
    ("JPCA", "https://www.jpca.or.jp/news/feed/"),
    # --- 海外PCB専門 ---
    ("PCB007", "https://pcb.iconnect007.com/rss"),
    ("SMT007", "https://smt.iconnect007.com/rss"),
    ("Design007", "https://design.iconnect007.com/rss"),
    ("Flex007", "https://flex.iconnect007.com/rss"),
    # --- 電子部品・半導体 ---
    ("EE Times", "https://www.eetimes.com/feed/"),
    ("EDN", "https://www.edn.com/feed/"),
    ("Semiconductor Engineering", "https://semiengineering.com/feed/"),
    ("Electronics Weekly", "https://www.electronicsweekly.com/feed/"),
    # --- 表面実装・製造装置 ---
    ("CircuitNet", "https://www.circuitnet.com/rss.xml"),
    ("EPSNews", "https://epsnews.com/feed/"),
    ("Global SMT & Packaging", "https://globalsmt.net/feed/"),
]

# PCB専門サイト（キーワードフィルタなしで全記事取得）
PCB_UNFILTERED_SOURCES = {
    "JPCA", "PCB007", "SMT007", "Design007", "Flex007",
    "CircuitNet", "Global SMT & Packaging",
}

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


def _is_tech_related(title: str) -> bool:
    """AI＋幅広いテクノロジーキーワードでフィルタ"""
    lower = title.lower()
    return (
        any(kw in lower for kw in AI_KEYWORDS)
        or any(kw in lower for kw in TECH_KEYWORDS)
    )


async def fetch_hackernews(client: httpx.AsyncClient, limit: int = 40) -> list[NewsItem]:
    """Hacker News トップストーリーからテクノロジー関連記事を取得"""
    resp = await client.get(HN_TOP_URL)
    story_ids = resp.json()[:200]

    items: list[NewsItem] = []
    tasks = [client.get(HN_ITEM_URL.format(sid)) for sid in story_ids[:100]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            continue
        story = r.json()
        if not story or story.get("type") != "story":
            continue
        title = story.get("title", "")
        url = story.get("url", f"https://news.ycombinator.com/item?id={story['id']}")
        if _is_tech_related(title):
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
    """プリント配線板・電子実装業界のニュースを取得"""
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
                    # PCB専門サイトはフィルタなしで全記事取得
                    if source_name in PCB_UNFILTERED_SOURCES or _is_pcb_related(title, summary):
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
