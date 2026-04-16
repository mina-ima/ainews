"""Google Gemini / Groq API でニュースを日本語要約・構造化"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

from google import genai
from groq import Groq

from .search import NewsItem

_LAST_MODEL_FILE = Path.home() / ".cache" / "ainews" / "last_model.txt"

JST = timezone(timedelta(hours=9))

SYSTEM_PROMPT = """\
あなたはテクノロジー展示会の専属レポーターです。
毎日テクノロジー展示会を巡回して情報収集しているように、AI・先端技術・製造業界の幅広いニュースを読者に届けてください。
AIだけでなく、「こんなことができるようになった」「こんなものが実現できた」という技術的ブレイクスルーや新製品の情報も重視します。

## 出力フォーマット (JSON)

```json
{
  "highlights": [
    {
      "title": "日本語タイトル",
      "category": "カテゴリ名",
      "summary": "2-3文の日本語要約",
      "importance": 5,
      "source_title": "元記事の英語タイトル",
      "source_url": "URL"
    }
  ],
  "trend_summary": "今日のテクノロジー業界の全体的な動向を3-5文で日本語解説"
}
```

## カテゴリ一覧（以下から選択）
- LLM・生成AI
- AI研究
- AIプロダクト
- AI規制・政策
- 半導体・チップ
- プリント基板・電子実装
- ロボティクス・自動化
- エネルギー・環境技術
- 宇宙・航空
- 医療・バイオ
- 材料・ナノテク
- 3Dプリンティング・製造
- 通信・ネットワーク
- 量子コンピューティング
- ソフトウェア・開発ツール
- その他先端技術

## ルール
- highlights は重要度の高い順に最大20件
- importance は1-5のスケール（5が最重要）
- 同じトピックの重複記事はまとめる
- 推測ではなく記事の内容に基づいて要約する
- **バランス重視**: AI系だけに偏らず、各分野からまんべんなく選出する。特にプリント基板・電子実装分野のニュースがあれば必ず含める
- 「世界初」「画期的」「実用化」「量産開始」「新素材」「新工法」など技術的ブレイクスルーは優先的に取り上げる
- **全ての出力は日本語で行うこと**。英語の記事タイトルや専門用語はわかりやすく日本語に翻訳する
- 要約は技術に詳しくない人でも理解できるよう、平易な日本語で書く。「何がすごいのか」「何が変わるのか」を伝える
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


import re

_MODEL_PATTERN = re.compile(r"^gemini-[\d.]+-flash(?:-lite|-8b|-\d+b)?$")
_EXCLUDE_KW = ["tts", "image", "vision", "preview"]


def _parse_model_version(name: str) -> tuple[float, str]:
    m = re.match(r"^gemini-([\d.]+)-flash(.*)$", name)
    return (float(m.group(1)), m.group(2)) if m else (0.0, "")


def _load_last_model() -> str | None:
    try:
        return _LAST_MODEL_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def _save_last_model(model: str) -> None:
    _LAST_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LAST_MODEL_FILE.write_text(model)


def _discover_models(client: genai.Client) -> list[str]:
    """フォールバック順: 前回成功モデル → 1つ前バージョン → 未来の新バージョン"""
    last_model = _load_last_model()

    try:
        all_models = []
        for m in client.models.list():
            short = m.name.replace("models/", "")
            if any(kw in short.lower() for kw in _EXCLUDE_KW):
                continue
            if _MODEL_PATTERN.match(short):
                all_models.append(short)
    except Exception:
        return [last_model] if last_model else ["gemini-2.5-flash"]

    if not all_models:
        return [last_model] if last_model else ["gemini-2.5-flash"]

    # 前回成功モデルの基準バージョンを決定
    if last_model:
        base_ver, _ = _parse_model_version(last_model)
    else:
        base_ver = max((_parse_model_version(m)[0] for m in all_models), default=0.0)

    # バージョンごとに分類
    all_vers = sorted({_parse_model_version(m)[0] for m in all_models}, reverse=True)
    one_back_ver = next((v for v in all_vers if v < base_ver), None)

    same, back, future = [], [], []
    for m in all_models:
        if last_model and m == last_model:
            continue  # 先頭に別途追加するので除外
        ver, _ = _parse_model_version(m)
        if ver == base_ver:
            same.append(m)
        elif one_back_ver is not None and ver == one_back_ver:
            back.append(m)
        elif ver > base_ver:
            future.append(m)

    same.sort(key=lambda m: (_parse_model_version(m)[1], m))
    back.sort(key=lambda m: (_parse_model_version(m)[1], m))
    future.sort(key=lambda m: (-_parse_model_version(m)[0], _parse_model_version(m)[1], m))

    result = []
    if last_model:
        result.append(last_model)
    result += same + back + future

    # 重複除去（順序保持）
    seen = set()
    result = [m for m in result if not (m in seen or seen.add(m))]

    print(f"  モデル試行順: {result}")
    if last_model:
        print(f"  (前回成功: {last_model})")
    return result


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
        models = _discover_models(client)
        for model in models:
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
                _save_last_model(model)
                return json.loads(response.text)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    print(f"  {model}: レート制限、次のモデルへ")
                    continue
                if "404" in error_msg or "NOT_FOUND" in error_msg:
                    continue
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    print(f"  {model}: サービス利用不可、次のモデルへ")
                    continue
                print(f"  Gemini エラー ({model}): {e}")
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
        "type: source",
        "source_url: \"\"",
        "author: AI自動収集",
        f"captured: {date}",
        "tags:",
        "  - daily-news",
        "  - AI",
        "  - technology",
        "  - PCB",
        "  - manufacturing",
        "---",
        "",
        f"# テクノロジー・デイリーレポート {date}（{weekday}）",
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
            lines.append("")
            lines.append("- [ ] 興味あり")
            lines.append("")
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

    parts = [f"{date}、{weekday}曜日のテクノロジー・デイリーレポートです。"]

    highlights = data.get("highlights", [])
    for i, h in enumerate(highlights[:10], 1):
        parts.append(f"第{i}位。{h['title']}。{h.get('summary', '')}")

    trend = data.get("trend_summary", "")
    if trend:
        parts.append(f"最後に、今日の注目ポイントです。{trend}")

    parts.append("以上、本日のテクノロジーレポートでした。")

    return "\n\n".join(parts)
