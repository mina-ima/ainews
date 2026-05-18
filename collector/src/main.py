"""AI Daily News - メインオーケストレーション"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .search import collect_news
from .summarize import summarize_news, generate_markdown, generate_tts_text
from .tts import generate_mp3
from .deepdive import load_interests, build_prompt_section, build_markdown_section

JST = timezone(timedelta(hours=9))
ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # ~/AI/ainews/
ARTICLES_DIR = ROOT_DIR / "articles"
HIGHLIGHTS_CACHE = ARTICLES_DIR / "highlights_cache.json"
RECENT_DAYS = 3


def _load_recent_stories() -> list[dict]:
    """過去RECENT_DAYS日分のハイライトタイトル・URLを返す"""
    if not HIGHLIGHTS_CACHE.exists():
        return []
    try:
        cache = json.loads(HIGHLIGHTS_CACHE.read_text())
    except Exception:
        return []
    cutoff = (datetime.now(JST) - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    stories: list[dict] = []
    for entry in cache.get("entries", []):
        if entry.get("date", "") >= cutoff:
            stories.extend(entry.get("stories", []))
    return stories


def _save_highlights_cache(date: str, highlights: list[dict]) -> None:
    """当日のハイライトをキャッシュに追記し、7日超のエントリを削除する"""
    if HIGHLIGHTS_CACHE.exists():
        try:
            cache = json.loads(HIGHLIGHTS_CACHE.read_text())
        except Exception:
            cache = {"entries": []}
    else:
        cache = {"entries": []}

    cutoff = (datetime.now(JST) - timedelta(days=7)).strftime("%Y-%m-%d")
    cache["entries"] = [e for e in cache["entries"] if e.get("date", "") >= cutoff]
    cache["entries"] = [e for e in cache["entries"] if e.get("date") != date]
    cache["entries"].append({
        "date": date,
        "stories": [
            {"title": h.get("title", ""), "source_url": h.get("source_url", "")}
            for h in highlights
        ],
    })
    HIGHLIGHTS_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


async def run() -> None:
    # AINEWS_TARGET_DATE で過去日を指定して再生成可能 (障害復旧用)
    date = os.environ.get("AINEWS_TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
    print(f"=== AI Daily News: {date} ===")

    # 1. ニュース収集
    print("Step 1: ニュース収集中...")
    items = await collect_news()
    print(f"  → {len(items)}件のニュースを取得")

    if not items:
        print("ニュースが見つかりませんでした。終了します。")
        return

    # 2. 興味アリ深堀りコンテキストを読み込み
    interests = load_interests()
    interests_section = build_prompt_section(interests)
    if interests:
        print(f"  (過去30日の興味アリ: {len(interests)}件を深堀り対象として要約に注入)")

    # 3. Gemini で要約（過去3日の既出ニュースを除外）
    print("Step 2: AI要約中...")
    recent_stories = _load_recent_stories()
    if recent_stories:
        print(f"  (過去{RECENT_DAYS}日間の既出ニュース: {len(recent_stories)}件を除外対象として渡す)")
    data = await summarize_news(items, recent_stories, interests_section=interests_section)
    highlights = data.get("highlights", [])
    print(f"  → {len(highlights)}件のハイライトを生成")

    # 最終ガード: 収集件数に対してハイライトが極端に少ない場合は警告を残す
    # (CI環境ではログに ::warning:: を出して気づけるようにする)
    MIN_FINAL_HIGHLIGHTS = 3
    if len(highlights) < MIN_FINAL_HIGHLIGHTS and len(items) >= 50:
        msg = (
            f"ハイライト数が異常に少ない (収集{len(items)}件 / 最終{len(highlights)}件)。"
            "LLMモデルの応答品質低下の可能性あり。"
        )
        print(f"::warning::{msg}" if os.environ.get("CI") else f"  [警告] {msg}")

    # 4. Markdown生成・保存（深堀り続報セクションも添付）
    print("Step 3: Markdown生成中...")
    deepdive_md = build_markdown_section(interests, highlights)
    md_content = generate_markdown(data, date, deepdive_section=deepdive_md)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    md_path = ARTICLES_DIR / f"{date}.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"  → {md_path}")

    # 4. TTS 音声生成
    print("Step 4: MP3音声生成中...")
    tts_text = generate_tts_text(data, date)
    mp3_path = str(ARTICLES_DIR / f"{date}.mp3")
    await generate_mp3(tts_text, mp3_path)
    mp3_size = os.path.getsize(mp3_path) / (1024 * 1024)
    print(f"  → {mp3_path} ({mp3_size:.1f}MB)")

    # 5. ハイライトキャッシュ保存
    _save_highlights_cache(date, highlights)

    # 6. index.json 更新
    print("Step 6: index.json 更新中...")
    index_path = ARTICLES_DIR / "index.json"
    if index_path.exists():
        index_data = json.loads(index_path.read_text())
    else:
        index_data = {"articles": []}

    # GitHub Releases URL（ローカル再生成時もデフォルトリポジトリを使う）
    repo = os.environ.get("GITHUB_REPOSITORY", "mina-ima/ainews")
    audio_url = f"https://github.com/{repo}/releases/download/news-{date}/{date}.mp3"

    entry = {
        "date": date,
        "title": f"AI・テクノロジーニュース {date}",
        "article_count": len(highlights),
        "audio_url": audio_url,
        "audio_size_mb": round(mp3_size, 1),
    }

    # 既存エントリを更新 or 追加
    index_data["articles"] = [a for a in index_data["articles"] if a["date"] != date]
    index_data["articles"].insert(0, entry)
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2))
    print(f"  → index.json 更新完了")

    # 6. GitHub Releases アップロード
    if repo and os.environ.get("CI"):
        # CI環境ではワークフローの別ステップでアップロードするためスキップ
        print("Step 6: MP3アップロードはワークフローステップで実行")
    elif not os.environ.get("CI"):
        print("Step 6: ローカル環境のためアップロードをスキップ")

    print(f"\n完了! {len(highlights)}件のニュースをまとめました。")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
