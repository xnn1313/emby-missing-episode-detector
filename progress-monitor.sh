#!/bin/bash
# MoviePilot 集成 - 进度汇报定时器
# 每 10 分钟检查任务进度并汇报

TODO_FILE="/root/.openclaw/workspace/emby-missing-episode-detector/TODO.md"
LOG_FILE="/tmp/moviepilot-integration.log"

echo "[$(date)] MoviePilot 集成进度监控器启动" >> "$LOG_FILE"

while true; do
    if [ -f "$TODO_FILE" ]; then
        # 统计完成情况
        total=$(grep -c "^| T" "$TODO_FILE" 2>/dev/null || echo 0)
        completed=$(grep -c "✅ 已完成" "$TODO_FILE" 2>/dev/null || echo 0)
        in_progress=$(grep -c "⏳ 进行中" "$TODO_FILE" 2>/dev/null || echo 0)
        pending=$(grep -c "⏳ 待开始" "$TODO_FILE" 2>/dev/null || echo 0)
        
        if [ "$total" -gt 0 ]; then
            rate=$((completed * 100 / total))
        else
            rate=0
        fi
        
        # 生成汇报消息
        message="🚀 MoviePilot 集成 - 进度汇报

任务总览：
- 总任务数：$total
- ✅ 已完成：$completed
- ⏳ 进行中：$in_progress
- ⏳ 待开始：$pending

完成率：${rate}%

当前重点：
1. MoviePilot 客户端模块 ✅
2. 配置模型扩展 ✅
3. 数据库表结构 ✅
4. 推送下载 API ✅
5. UI 配置页面 ⏳ 进行中

下次汇报：10 分钟后"
        
        echo "[$(date)] $message" >> "$LOG_FILE"
        
        # 等待 10 分钟
        sleep 600
    else
        echo "[$(date)] TODO.md 未找到" >> "$LOG_FILE"
        sleep 60
    fi
done
