#!/bin/bash
echo "启动 Emby 缺集检测系统..."
cd "$(dirname "$0")"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload 2>&1
