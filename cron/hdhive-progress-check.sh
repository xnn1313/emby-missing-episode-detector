#!/bin/bash
# HDHive 开发进度检查脚本
# 每 10 分钟执行一次

TASKS_FILE="/root/.openclaw/workspace/emby-missing-episode-detector/HDHIVE_TASKS.md"
LOG_FILE="/root/.openclaw/workspace/emby-missing-episode-detector/logs/hdhive-progress.log"

# 获取当前时间
NOW=$(date '+%Y-%m-%d %H:%M:%S')

# 计算进度
TOTAL_TASKS=$(grep -c "^\- \[" "$TASKS_FILE" 2>/dev/null || echo "0")
COMPLETED_TASKS=$(grep -c "^\- \[x\]" "$TASKS_FILE" 2>/dev/null || echo "0")

if [ "$TOTAL_TASKS" -gt 0 ]; then
    PROGRESS=$((COMPLETED_TASKS * 100 / TOTAL_TASKS))
else
    PROGRESS=0
fi

# 获取当前阶段
CURRENT_PHASE=$(grep -E "^## Phase|^### [0-9]" "$TASKS_FILE" | grep -B1 "⏳ 待开始" | head -1 | sed 's/## //' || echo "未开始")

# 记录日志
echo "[$NOW] 进度: $PROGRESS% ($COMPLETED_TASKS/$TOTAL_TASKS) - 当前阶段: $CURRENT_PHASE" >> "$LOG_FILE"

# 检查是否需要继续开发（进度 < 100%）
if [ "$PROGRESS" -lt 100 ]; then
    echo "[$NOW] 需要继续开发" >> "$LOG_FILE"
    # 触发消息提醒（通过 openclaw 命令）
    # 这里可以调用 openclaw 发送消息
fi

echo "进度检查完成: $PROGRESS%"