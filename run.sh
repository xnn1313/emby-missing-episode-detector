#!/bin/bash
# Emby 缺集检测系统 - 服务启动脚本
# 使用方法：./run.sh [start|stop|restart|status]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.uvicorn.pid"
LOG_FILE="$SCRIPT_DIR/logs/uvicorn.log"
PORT=8080

# 确保日志目录存在
mkdir -p "$SCRIPT_DIR/logs"

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "❌ 服务已在运行 (PID: $PID)"
            return 1
        fi
        rm -f "$PID_FILE"
    fi
    
    cd "$SCRIPT_DIR"
    echo "🚀 启动服务..."
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ 服务已启动 (PID: $PID, 端口：$PORT)"
        echo "📄 日志：$LOG_FILE"
    else
        echo "❌ 启动失败，查看日志：$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "⏹️  停止服务 (PID: $PID)..."
            kill "$PID" 2>/dev/null
            sleep 2
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
            fi
            rm -f "$PID_FILE"
            echo "✅ 服务已停止"
        else
            echo "⚠️  服务未运行，清理 PID 文件"
            rm -f "$PID_FILE"
        fi
    else
        # 尝试通过端口查找进程
        PID=$(lsof -t -i:$PORT 2>/dev/null | head -1)
        if [ -n "$PID" ]; then
            echo "⏹️  停止服务 (端口：$PORT, PID: $PID)..."
            kill "$PID" 2>/dev/null
            sleep 1
            echo "✅ 服务已停止"
        else
            echo "⚠️  服务未运行"
        fi
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ 服务运行中 (PID: $PID, 端口：$PORT)"
            return 0
        fi
    fi
    
    PID=$(lsof -t -i:$PORT 2>/dev/null | head -1)
    if [ -n "$PID" ]; then
        echo "✅ 服务运行中 (端口：$PORT, PID: $PID)"
        return 0
    fi
    
    echo "❌ 服务未运行"
    return 1
}

case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "用法：$0 {start|stop|restart|status}"
        exit 1
        ;;
esac
