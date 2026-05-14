#!/usr/bin/env python3
"""Obsidian Vault → repo の興味アリキャッシュ同期スクリプト

Obsidian の `30_Sources/ainews-*.md` に付いた `- [x] 興味あり` を抽出して
`articles/interests.json` に書き出す。CI（GitHub Actions）で深堀り機能を
有効化したい場合に commit して使う。

ローカル実行のみで利用するなら通常は不要（collector が直接 Vault を読む）。

使い方:
    cd ~/AI/ainews
    uv run --project collector python scripts/sync_interests.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# collector/src を import path に追加
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collector"))

from src.deepdive import load_interests, save_cache, DEFAULT_INTERESTS_CACHE


def main() -> None:
    items = load_interests()
    save_cache(items, DEFAULT_INTERESTS_CACHE)
    print(f"  {len(items)} 件の興味アリ項目を {DEFAULT_INTERESTS_CACHE} に保存しました")
    for it in items[:5]:
        print(f"    - [{it.date}] {it.title}")
    if len(items) > 5:
        print(f"    ... 他 {len(items) - 5} 件")


if __name__ == "__main__":
    main()
