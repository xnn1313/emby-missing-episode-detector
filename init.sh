#!/bin/bash
# Emby 缺集检测系统 - 启动脚本

set -e

# 进入项目目录
cd "$(dirname "$0")"

# 检查配置文件
if [ ! -f "config/.env" ]; then
    echo "⚠️  配置文件不存在，复制示例配置..."
    cp config/.env.example config/.env
    echo "请编辑 config/.env 填入 Emby 配置后重新运行"
    exit 1
fi

# 加载环境变量
export $(grep -v '^#' config/.env | xargs)

# 安装依赖
echo "📦 检查依赖..."
pip install -r requirements.txt -q

# 启动服务
echo "🚀 启动 Emby 缺集检测系统..."
echo "Web 界面：http://localhost:8080"
echo "API 文档：http://localhost:8080/docs"
echo ""

python3 main.py
