#!/bin/bash
# Mac起動時にObsidianへ未取得のAIニュースを全てダウンロード（差分同期）

REPO_DIR="$HOME/AI/ainews"
OBSIDIAN_DIR="$HOME/Obsidian/00_Inbox"
LOG="/tmp/ainews-download.log"

echo "$(date): ainews download start" >> "$LOG"

# リポジトリ更新
cd "$REPO_DIR" && git pull --ff-only >> "$LOG" 2>&1

# 未取得のmdファイルを全てコピー
COUNT_MD=0
for MD_FILE in "$REPO_DIR/articles/"*.md; do
    [ -f "$MD_FILE" ] || continue
    BASENAME=$(basename "$MD_FILE")
    [ "$BASENAME" = "index.json" ] && continue
    DEST="$OBSIDIAN_DIR/ainews-${BASENAME}"
    if [ ! -f "$DEST" ]; then
        cp "$MD_FILE" "$DEST"
        COUNT_MD=$((COUNT_MD + 1))
        echo "  md: $BASENAME" >> "$LOG"
    fi
done

# 未取得のMP3を全てダウンロード
COUNT_MP3=0
if command -v python3 &>/dev/null && [ -f "$REPO_DIR/articles/index.json" ]; then
    python3 -c "
import json
with open('$REPO_DIR/articles/index.json') as f:
    data = json.load(f)
for a in data.get('articles', []):
    url = a.get('audio_url', '')
    if url:
        print(a['date'], url)
" 2>/dev/null | while read -r DATE AUDIO_URL; do
        DEST="$OBSIDIAN_DIR/ainews-${DATE}.mp3"
        if [ -n "$AUDIO_URL" ] && [ ! -f "$DEST" ]; then
            curl -sL "$AUDIO_URL" -o "$DEST" 2>> "$LOG"
            COUNT_MP3=$((COUNT_MP3 + 1))
            echo "  mp3: ainews-${DATE}.mp3" >> "$LOG"
        fi
    done
fi

echo "$(date): ainews download done (md: $COUNT_MD new)" >> "$LOG"
