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
    echo "" >> "$LOG_FILE"
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') start =====" >> "$LOG_FILE"
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT >> "$LOG_FILE" 2>&1 &
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
    # 先清理所有占用端口的进程
    PIDS=$(lsof -t -i:$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⏹️  清理端口 $PORT 占用的进程..."
        echo "$PIDS" | xargs kill -9 2>/dev/null
        sleep 2
    fi
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "⏹️  停止服务 (PID: $PID)..."
            kill -9 "$PID" 2>/dev/null
            sleep 1
        fi
        rm -f "$PID_FILE"
    fi
    
    # 再次确认端口已释放
    PIDS=$(lsof -t -i:$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⚠️  强制清理残留进程..."
        echo "$PIDS" | xargs kill -9 2>/dev/null
        sleep 2
    fi
    
    echo "✅ 服务已停止"
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
