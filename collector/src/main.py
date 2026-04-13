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
from .upload import upload_to_release

JST = timezone(timedelta(hours=9))
ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # ~/AI/ainews/
ARTICLES_DIR = ROOT_DIR / "articles"


async def run() -> None:
    date = datetime.now(JST).strftime("%Y-%m-%d")
    print(f"=== AI Daily News: {date} ===")

    # 1. ニュース収集
    print("Step 1: ニュース収集中...")
    items = await collect_news()
    print(f"  → {len(items)}件のニュースを取得")

    if not items:
        print("ニュースが見つかりませんでした。終了します。")
        return

    # 2. Gemini で要約
    print("Step 2: AI要約中...")
    data = await summarize_news(items)
    highlights = data.get("highlights", [])
    print(f"  → {len(highlights)}件のハイライトを生成")

    # 3. Markdown生成・保存
    print("Step 3: Markdown生成中...")
    md_content = generate_markdown(data, date)
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

    # 5. index.json 更新
    print("Step 5: index.json 更新中...")
    index_path = ARTICLES_DIR / "index.json"
    if index_path.exists():
        index_data = json.loads(index_path.read_text())
    else:
        index_data = {"articles": []}

    # GitHub Releases URL（CI環境ではアップロード後に更新）
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    audio_url = ""
    if repo:
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

    # 6. GitHub Releases アップロード（CI環境のみ）
    if repo and os.environ.get("CI"):
        print("Step 6: GitHub Releases にMP3アップロード中...")
        url = upload_to_release(mp3_path, date, repo)
        print(f"  → {url}")
        # アップロード後にローカルMP3を削除（gitにcommitしないため）
        os.remove(mp3_path)
        print("  → ローカルMP3削除")
    else:
        print("Step 6: ローカル環境のためアップロードをスキップ")

    print(f"\n完了! {len(highlights)}件のニュースをまとめました。")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
