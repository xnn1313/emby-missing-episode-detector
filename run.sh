#!/bin/bash
while true; do
    echo "[$(date)] 启动服务..." >> /tmp/emby-monitor.log
    python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 >> /tmp/emby-monitor.log 2>&1
    echo "[$(date)] 服务退出，5 秒后重启..." >> /tmp/emby-monitor.log
    sleep 5
done
