#!/bin/bash
# Mac起動時にObsidianへ未取得のAIニュースを全てダウンロード（差分同期）

REPO_DIR="$HOME/AI/ainews"
# Inbox に置き、/obsidian のトリアージ（要約・Topic への知識化）を経てから 30_Sources へ移す
INBOX_DIR="$HOME/Obsidian/00_Inbox"
OBSIDIAN_DIR="$HOME/Obsidian/30_Sources"
# 共有の /tmp は他ユーザーが同名の symlink を先に置ける（追記先を乗っ取られる）
LOG="$HOME/Library/Logs/ainews-download.log"
mkdir -p "$(dirname "$LOG")"

echo "$(date): ainews download start" >> "$LOG"

# リポジトリ更新
cd "$REPO_DIR" && git pull --ff-only >> "$LOG" 2>&1

# 未取得のmdファイルを全てコピー
COUNT_MD=0
for MD_FILE in "$REPO_DIR/articles/"*.md; do
    [ -f "$MD_FILE" ] || continue
    BASENAME=$(basename "$MD_FILE")
    [ "$BASENAME" = "index.json" ] && continue
    NAME="ainews-${BASENAME}"
    if [ ! -f "$INBOX_DIR/$NAME" ] && [ ! -f "$OBSIDIAN_DIR/$NAME" ]; then
        cp "$MD_FILE" "$INBOX_DIR/$NAME"
        COUNT_MD=$((COUNT_MD + 1))
        echo "  md: $BASENAME" >> "$LOG"
    fi
done
# MP3 は取得しない（ユーザー方針）

echo "$(date): ainews download done (md: $COUNT_MD new)" >> "$LOG"

# Obsidian側でチェックした「[x] 興味あり」を articles/interests.json に同期
# （CI実行時の深堀り機能で参照される）
if [ -d "$OBSIDIAN_DIR" ] && command -v uv &>/dev/null; then
    cd "$REPO_DIR" && uv run --project collector python scripts/sync_interests.py >> "$LOG" 2>&1 || true
fi
