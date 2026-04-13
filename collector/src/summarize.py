"""Google Gemini / Groq API でニュースを日本語要約・構造化"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

from google import genai
from groq import Groq

from .search import NewsItem

JST = timezone(timedelta(hours=9))

SYSTEM_PROMPT = """\
あなたはAI・テクノロジーニュースの編集者です。
与えられたニュース一覧を分析し、重要度の高い順に整理して日本語で要約してください。

## 出力フォーマット (JSON)

```json
{
  "highlights": [
    {
      "title": "日本語タイトル",
      "category": "LLM・生成AI / AI研究 / AIプロダクト / AI規制 / 半導体・HW / ソフトウェア・ツール / プリント配線板・実装",
      "summary": "2-3文の日本語要約",
      "importance": 5,
      "source_title": "元記事の英語タイトル",
      "source_url": "URL"
    }
  ],
  "trend_summary": "今日のAI業界の全体的な動向を3-5文で日本語解説"
}
```

## ルール
- highlights は重要度の高い順に最大12件
- importance は1-5のスケール（5が最重要）
- 同じトピックの重複記事はまとめる
- 推測ではなく記事の内容に基づいて要約する
- カテゴリは上記7種のいずれかを使用
- プリント配線板（PCB/PWB）・電子実装関連のニュースがあれば必ず含める
- **全ての出力は日本語で行うこと**。英語の記事タイトルや専門用語はわかりやすく日本語に翻訳する
- 要約は技術に詳しくない人でも理解できるよう、平易な日本語で書く
- 固有名詞（企業名・製品名）はカタカナ表記し、初出時に英語を併記する（例: オープンAI（OpenAI）)
- source_title は元記事の原語タイトルをそのまま保持する
"""


def _build_user_prompt(items: list[NewsItem]) -> str:
    lines = ["# 本日のニュース一覧\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"## {i}. {item.title}")
        lines.append(f"- Source: {item.source}")
        lines.append(f"- URL: {item.url}")
        if item.summary:
            lines.append(f"- Snippet: {item.summary}")
        lines.append("")
    return "\n".join(lines)


GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _get_gemini_keys() -> list[str]:
    single = os.environ.get("GOOGLE_API_KEY", "")
    if single:
        return [single]
    return [v for k, v in sorted(os.environ.items()) if k.startswith("GEMINI_KEY_") and v]


async def _try_gemini(user_prompt: str) -> dict | None:
    api_keys = _get_gemini_keys()
    if not api_keys:
        return None

    for api_key in api_keys:
        client = genai.Client(api_key=api_key)
        for model in GEMINI_MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.3,
                    },
                )
                print(f"  (使用: Gemini {model})")
                return json.loads(response.text)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    continue
                if "404" in error_msg or "NOT_FOUND" in error_msg:
                    continue
                print(f"  Gemini エラー: {e}")
    return None


async def _try_groq(user_prompt: str) -> dict | None:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        print("  (使用: Groq llama-3.3-70b)")
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"  Groq エラー: {e}")
        return None


async def summarize_news(items: list[NewsItem]) -> dict:
    """ニュースを要約（Gemini → Groq フォールバック）"""
    user_prompt = _build_user_prompt(items)

    result = await _try_gemini(user_prompt)
    if result:
        return result

    result = await _try_groq(user_prompt)
    if result:
        return result

    raise RuntimeError(
        "全てのLLM APIでエラー。GOOGLE_API_KEY/GEMINI_KEY_* または GROQ_API_KEY を設定してください。\n"
        "Groq APIキーは https://console.groq.com で無料取得できます。"
    )


def generate_markdown(data: dict, date: str | None = None) -> str:
    if date is None:
        date = datetime.now(JST).strftime("%Y-%m-%d")

    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = weekdays[dt.weekday()]

    lines = [
        "---",
        f"date: {date}",
        "tags:",
        "  - daily-news",
        "  - AI",
        "  - technology",
        "---",
        "",
        f"# AI・テクノロジーニュース {date}（{weekday}）",
        "",
    ]

    highlights = data.get("highlights", [])
    if highlights:
        current_category = ""
        for h in highlights:
            cat = h.get("category", "その他")
            if cat != current_category:
                current_category = cat
                lines.append(f"## {cat}")
                lines.append("")

            importance = "★" * h.get("importance", 3)
            lines.append(f"### {h['title']}")
            lines.append(f"**重要度**: {importance}")
            lines.append("")
            lines.append(h.get("summary", ""))
            lines.append("")
            source_title = h.get("source_title", "Source")
            source_url = h.get("source_url", "")
            lines.append(f"- Source: [{source_title}]({source_url})")
            lines.append("")
            lines.append("---")
            lines.append("")

    trend = data.get("trend_summary", "")
    if trend:
        lines.append("## 今日の注目ポイント")
        lines.append("")
        lines.append(trend)
        lines.append("")

    lines.append("---")
    lines.append("*このニュースはAIにより自動収集・要約されました*")

    return "\n".join(lines)


def generate_tts_text(data: dict, date: str | None = None) -> str:
    if date is None:
        date = datetime.now(JST).strftime("%Y-%m-%d")

    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = weekdays[dt.weekday()]

    parts = [f"{date}、{weekday}曜日のAI・テクノロジーニュースです。"]

    highlights = data.get("highlights", [])
    for i, h in enumerate(highlights[:8], 1):
        parts.append(f"第{i}位。{h['title']}。{h.get('summary', '')}")

    trend = data.get("trend_summary", "")
    if trend:
        parts.append(f"最後に、今日の注目ポイントです。{trend}")

    parts.append("以上、本日のAIニュースでした。")

    return "\n\n".join(parts)
