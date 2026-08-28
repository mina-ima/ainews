"""深堀り一致判定の最小チェック: uv run python test_deepdive.py

2026-08-28 に「15記事中14件が深堀り扱い」になった回帰を防ぐ。
原因は (1) 数字だけのトークン、(2) 汎用カテゴリ語、(3) 部分文字列一致、(4) 1件一致で採用。
"""

from src.deepdive import (
    MIN_KEYWORD_HITS,
    InterestItem,
    build_markdown_section,
    count_keyword_hits,
    extract_keywords,
)


def _interest(title: str) -> InterestItem:
    return InterestItem(title=title, category="AI", date="2026-08-01")


def test_numeric_only_tokens_dropped():
    kw = extract_keywords([_interest("コンテキスト100万トークン対応の謎のモデル")])
    assert "100" not in kw  # 「100社」「100テラバイト」に当たってしまう
    assert "コンテキスト" in kw


def test_generic_category_words_dropped():
    kw = extract_keywords([_interest("次世代の自律型エージェントがオープンソースで公開")])
    for generic in ("次世代", "自律型", "エージェント", "オープンソース"):
        assert generic not in kw, generic


def test_ascii_keyword_requires_word_boundary():
    kw = extract_keywords([_interest("オープンAIの最上位AI「GPT-5.6 Sol」")])
    assert "sol" in kw
    # "Sol" が "Absolics" の一部に当たってはいけない
    assert count_keyword_hits("アブソリクス（Absolics）のガラス基板", {"sol"}) == 0
    assert count_keyword_hits("GPT-5.6 Sol が不正行為", {"sol"}) == 1


def test_single_weak_hit_is_not_deep_dive():
    items = [_interest("グーグル、2028年までに独自TPU製造を目指す")]
    weak = {"title": "各社がAIリスクに警鐘", "summary": "グーグルなど100社が共同声明", "source_url": "u"}
    assert build_markdown_section(items, [weak]) == ""  # 1件一致では載せない


def test_multiple_hits_becomes_deep_dive():
    items = [_interest("エヌビディア（NVIDIA）がストレージをGPUに直結")]
    strong = {
        "title": "エヌビディア、ハギング・フェイスを130億ドルで買収合意",
        "summary": "エヌビディア（NVIDIA）はAIモデル共有基盤を買収する。",
        "source_url": "u",
        "category": "AIプロダクト",
    }
    out = build_markdown_section(items, [strong])
    assert "## 深堀り" in out
    assert "ハギング・フェイス" in out
    assert count_keyword_hits(strong["title"] + strong["summary"], extract_keywords(items)) >= MIN_KEYWORD_HITS


if __name__ == "__main__":
    test_numeric_only_tokens_dropped()
    test_generic_category_words_dropped()
    test_ascii_keyword_requires_word_boundary()
    test_single_weak_hit_is_not_deep_dive()
    test_multiple_hits_becomes_deep_dive()
    print("ok")
