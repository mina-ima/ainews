"""興味アリ深堀り: Obsidian Vault の `[x] 興味あり` を読み戻し、続報・拡張収集の文脈を生成する。

- ローカル実行時: `OBSIDIAN_VAULT` 環境変数 or `~/Obsidian/30_Sources/ainews-*.md` を走査
- CI 実行時: `articles/interests.json`（事前生成キャッシュ）があれば利用
- 抽出された関心トピックを LLM 要約プロンプトと Markdown 出力の両方に流し込む
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

DEFAULT_VAULT_SOURCES = Path.home() / "Obsidian" / "30_Sources"
DEFAULT_INTERESTS_CACHE = (
    Path(__file__).resolve().parent.parent.parent / "articles" / "interests.json"
)
RECENT_WINDOW_DAYS = 30
MAX_INTERESTS_FOR_PROMPT = 25

# 「深堀り」に載せるのに必要な、興味アリ由来キーワードの一致数。
# 1 だと汎用語 1 個の偶然一致で通ってしまい、実測で 15 記事中 14 件が該当して
# フィルタとして機能しなかった（2026-08-28）。2 以上を要求する。
MIN_KEYWORD_HITS = 2

# 興味タイトルから「固有名詞」候補だけを抽出するための除外語。
# 下段は 2026-08-28 の実測で誤マッチ源になっていた汎用語（どのAI記事にも出る
# カテゴリ語であって、読者固有の関心を示さない）。
_STOPWORDS = {
    "テスト", "システム", "サービス", "プロジェクト", "ニュース", "オープン",
    "ソフト", "ハード", "デバイス", "プラットフォーム", "メーカー", "ユーザー",
    "アップデート", "リリース", "サポート", "コンテンツ", "ビジネス", "コンセプト",
    "test", "news", "open", "soft", "user", "system",
    "次世代", "自律型", "実用的", "自動化", "超小型", "高性能", "高効率", "世界初",
    "最新型", "開発者", "研究者", "技術者", "大規模", "小規模", "国内外",
    "リアルタイム", "ハードウェア", "ソフトウェア", "オープンソース", "ロボット",
    "ウェアラブル", "データベース", "ネットワーク", "プロセス", "エージェント",
    "テクノロジー", "インターフェース", "アルゴリズム", "セキュリティ", "クラウド",
    "エネルギー", "ディスプレイ", "バッテリー", "スマートフォン", "コンピュータ",
}

# 英字: 5文字以上の英単語（Anthropic 等）／大文字始まり3文字以上（NVIDIA, GPT-5.6 等）
# 数字始まり（2nm, 3D 等）／カタカナ4文字以上／漢字3文字以上
_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9.\-]{4,}"
    r"|[A-Z][A-Za-z0-9.\-]{2,}"
    r"|[0-9][A-Za-z0-9.\-]{2,}"
    r"|[ァ-ヴー]{4,}"
    r"|[一-龠]{3,}"
)
_HAS_LETTER_RE = re.compile(r"[A-Za-z぀-ヿ一-鿿]")
_ASCII_KEYWORD_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def extract_keywords(items: list[InterestItem]) -> set[str]:
    """興味アリのタイトル群から、続報判定に使う固有名詞候補を抜き出す。"""
    keywords: set[str] = set()
    for it in items:
        for token in _TOKEN_RE.findall(it.title):
            tok = token.lower()
            if tok in _STOPWORDS or token in _STOPWORDS:
                continue
            # 数字だけのトークン（「100万トークン」の 100 等）は捨てる。
            # 残すと「100社」「100テラバイト」に当たって無意味な一致を量産する。
            if not _HAS_LETTER_RE.search(token):
                continue
            keywords.add(tok)
    return keywords


def count_keyword_hits(haystack: str, keywords: set[str]) -> int:
    """本文中に現れた興味アリ由来キーワードの種類数を数える。"""
    lower = haystack.lower()
    hits = 0
    for k in keywords:
        if _ASCII_KEYWORD_RE.match(k):
            # 英数字は語境界を要求する。部分文字列一致だと "Sol" が "Absolics" に
            # 当たるような事故が起きる（2026-08-28 実測）。
            if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", lower):
                hits += 1
        elif k in lower:
            hits += 1
    return hits

# `### タイトル` の直下〜次の `### or ##` までを 1 記事ブロックとみなす
_BLOCK_RE = re.compile(
    r"^###\s+(?P<title>[^\n]+)\n(?P<body>.*?)(?=^##\s|^---\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_DATE_RE = re.compile(r"ainews-(\d{4}-\d{2}-\d{2})\.md$")
_CATEGORY_HEADING_RE = re.compile(r"^##\s+([^\n]+)$", re.MULTILINE)


@dataclass
class InterestItem:
    title: str
    category: str
    date: str  # YYYY-MM-DD
    source_url: str = ""
    importance: int = 3


def _parse_one_file(md_path: Path) -> list[InterestItem]:
    """1 つの ainews-YYYY-MM-DD.md から `[x] 興味あり` を抽出"""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return []

    m = _DATE_RE.search(md_path.name)
    date = m.group(1) if m else ""

    # カテゴリ見出し位置を記録
    cat_positions: list[tuple[int, str]] = [
        (mm.start(), mm.group(1).strip()) for mm in _CATEGORY_HEADING_RE.finditer(text)
    ]

    def _category_at(pos: int) -> str:
        current = "その他"
        for p, name in cat_positions:
            if p <= pos:
                current = name
            else:
                break
        return current

    items: list[InterestItem] = []
    for block in _BLOCK_RE.finditer(text):
        body = block.group("body")
        if "- [x] 興味あり" not in body:
            continue
        title = block.group("title").strip()
        importance = body.count("★") if "★" in body else 3
        url_m = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", body)
        url = url_m.group(1) if url_m else ""
        items.append(InterestItem(
            title=title,
            category=_category_at(block.start()),
            date=date,
            source_url=url,
            importance=min(importance, 5) or 3,
        ))
    return items


def _scan_vault(vault_sources: Path, cutoff_date: str) -> list[InterestItem]:
    """Vault 内 ainews-*.md を走査"""
    if not vault_sources.is_dir():
        return []
    out: list[InterestItem] = []
    for p in sorted(vault_sources.glob("ainews-*.md")):
        m = _DATE_RE.search(p.name)
        if not m or m.group(1) < cutoff_date:
            continue
        out.extend(_parse_one_file(p))
    return out


def _load_cache(cache_path: Path) -> list[InterestItem]:
    if not cache_path.exists():
        return []
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        return [InterestItem(**d) for d in raw.get("items", [])]
    except Exception:
        return []


def save_cache(items: list[InterestItem], cache_path: Path = DEFAULT_INTERESTS_CACHE) -> None:
    """sync_interests.py 等から呼び出してリポジトリ内にキャッシュを書く"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(JST).isoformat(),
                "items": [asdict(it) for it in items],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_interests(
    vault_sources: Path | None = None,
    cache_path: Path | None = None,
    window_days: int = RECENT_WINDOW_DAYS,
) -> list[InterestItem]:
    """興味アリ項目を読み込む。Vault > cache の優先順。"""
    vault_sources = vault_sources or Path(
        os.environ.get("OBSIDIAN_VAULT_SOURCES", str(DEFAULT_VAULT_SOURCES))
    )
    cache_path = cache_path or DEFAULT_INTERESTS_CACHE

    cutoff = (datetime.now(JST) - timedelta(days=window_days)).strftime("%Y-%m-%d")

    items = _scan_vault(vault_sources, cutoff_date=cutoff)
    if items:
        return items
    return [it for it in _load_cache(cache_path) if it.date >= cutoff]


def build_prompt_section(items: list[InterestItem]) -> str:
    """要約 LLM プロンプトに添える「深堀り対象」セクションを生成"""
    if not items:
        return ""

    # 重要度降順 → 日付降順で上位を抜粋
    items_sorted = sorted(items, key=lambda x: (-x.importance, x.date), reverse=False)
    items_sorted = sorted(items, key=lambda x: (x.importance, x.date), reverse=True)
    top = items_sorted[:MAX_INTERESTS_FOR_PROMPT]

    # カテゴリ集約で読者の関心スプレッドを示す
    by_category: dict[str, list[InterestItem]] = {}
    for it in top:
        by_category.setdefault(it.category, []).append(it)

    lines = [
        "# 深堀り対象（読者が継続的に関心を示しているテーマ）",
        "",
        "以下は過去最大30日間に読者が `興味あり` チェックを入れた記事です。",
        "本日のニュースの中に **これらの続報・関連企業動向・規制影響・市場波及・実証事例** が見つかった場合は、",
        "通常記事より一段深い文脈（背景・利害関係者・自社業務インパクト想定）を summary に織り込み、",
        "importance を 1 段階引き上げて優先的に highlights に含めてください。",
        "新規記事が無い場合でも、関連企業・関連製品名がタイトルや snippet に出現していれば積極的に拾うこと。",
        "",
    ]
    for cat, lst in by_category.items():
        lines.append(f"## {cat}")
        for it in lst[:10]:
            tag = "★" * max(1, it.importance)
            lines.append(f"- [{it.date}] {tag} {it.title}")
        lines.append("")
    return "\n".join(lines)


def build_markdown_section(items: list[InterestItem], today_highlights: list[dict]) -> str:
    """本日の highlights のうち、興味アリと意味的に重複しそうなものを別途並べる
    （単純なキーワード一致ベースのライト実装。LLM 側で本格処理する想定。）"""
    if not items or not today_highlights:
        return ""

    keywords = extract_keywords(items)

    matched: list[dict] = []
    for h in today_highlights:
        haystack = h.get("title", "") + " " + h.get("summary", "")
        if count_keyword_hits(haystack, keywords) >= MIN_KEYWORD_HITS:
            matched.append(h)

    if not matched:
        return ""

    lines = [
        "## 深堀り（過去の興味アリ続報）",
        "",
        "読者が `興味あり` チェックを付けた過去テーマに関連する本日の記事:",
        "",
    ]
    for h in matched:
        url = h.get("source_url", "")
        title = h.get("title", "")
        cat = h.get("category", "")
        lines.append(f"- **{title}**（{cat}） — [元記事]({url})")
    lines.append("")
    return "\n".join(lines)
