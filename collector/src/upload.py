"""GitHub Releases へのMP3アップロード"""

from __future__ import annotations

import subprocess


def upload_to_release(mp3_path: str, date: str, repo: str) -> str:
    """gh CLI で GitHub Release にMP3をアップロード"""
    tag = f"news-{date}"
    release_name = f"AI News {date}"

    # リリース作成（既存なら無視）
    subprocess.run(
        ["gh", "release", "create", tag, "--title", release_name,
         "--notes", f"AI・テクノロジーニュース {date}", "--repo", repo],
        capture_output=True,
    )

    # MP3アップロード
    subprocess.run(
        ["gh", "release", "upload", tag, mp3_path,
         "--clobber", "--repo", repo],
        check=True,
        capture_output=True,
    )

    # ダウンロードURL を返す
    result = subprocess.run(
        ["gh", "release", "view", tag, "--json", "assets",
         "--jq", ".assets[0].url", "--repo", repo],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
