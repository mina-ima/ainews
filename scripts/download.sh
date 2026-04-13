#!/bin/bash
# Mac起動時にObsidianへ最新AIニュースをダウンロード

REPO_DIR="$HOME/AI/ainews"
OBSIDIAN_DIR="$HOME/Obsidian/00_Inbox"
LOG="/tmp/ainews-download.log"

echo "$(date): ainews download start" >> "$LOG"

# リポジトリ更新
cd "$REPO_DIR" && git pull --ff-only >> "$LOG" 2>&1

# 最新mdをコピー
LATEST_MD=$(ls -t "$REPO_DIR/articles/"*.md 2>/dev/null | grep -v index | head -1)
if [ -n "$LATEST_MD" ]; then
    BASENAME=$(basename "$LATEST_MD")
    cp "$LATEST_MD" "$OBSIDIAN_DIR/ainews-${BASENAME}"
    echo "  md: $BASENAME" >> "$LOG"
fi

# 最新MP3をGitHub Releasesからダウンロード
if command -v python3 &>/dev/null && [ -f "$REPO_DIR/articles/index.json" ]; then
    AUDIO_INFO=$(python3 -c "
import json
with open('$REPO_DIR/articles/index.json') as f:
    data = json.load(f)
if data['articles']:
    a = data['articles'][0]
    print(a['date'], a.get('audio_url', ''))
" 2>/dev/null)

    DATE=$(echo "$AUDIO_INFO" | cut -d' ' -f1)
    AUDIO_URL=$(echo "$AUDIO_INFO" | cut -d' ' -f2)

    if [ -n "$AUDIO_URL" ] && [ ! -f "$OBSIDIAN_DIR/ainews-${DATE}.mp3" ]; then
        curl -sL "$AUDIO_URL" -o "$OBSIDIAN_DIR/ainews-${DATE}.mp3" 2>> "$LOG"
        echo "  mp3: ainews-${DATE}.mp3" >> "$LOG"
    fi
fi

echo "$(date): ainews download done" >> "$LOG"
