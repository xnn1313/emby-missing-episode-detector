#!/bin/bash
# 定时进度汇报脚本 - 每 10 分钟执行一次

PROJECT_DIR="/root/.openclaw/workspace/emby-missing-episode-detector"
FEATURE_FILE="$PROJECT_DIR/.claude-progress/feature_list.json"

# 检查功能列表
if [ -f "$FEATURE_FILE" ]; then
    TOTAL=$(grep -o '"id":' "$FEATURE_FILE" | wc -l)
    DONE=$(grep '"passes": true' "$FEATURE_FILE" | wc -l)
    
    if [ "$TOTAL" -gt 0 ]; then
        PROGRESS=$((DONE * 100 / TOTAL))
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 功能: $DONE/$TOTAL ($PROGRESS%)"
    fi
fi