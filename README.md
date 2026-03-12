# Emby 缺集检测系统

基于 MoviePilot 设计理念的 Emby 媒体库缺集检测工具，支持自动推送缺失剧集到 MoviePilot 下载。

## 功能特性

- 🔍 **自动检测** - 扫描 Emby 媒体库，识别缺失剧集
- 📊 **海报墙展示** - 直观的列表视图，支持排序、筛选、分页
- 🚀 **MoviePilot 集成** - 一键推送缺失剧集到 MoviePilot 自动下载
- 💾 **数据持久化** - 检测结果缓存，无需重复检测
- 🎯 **智能去重** - 自动识别 Emby 重复刮削的剧集
- 📱 **响应式设计** - 支持桌面和移动端访问

## 快速开始

### 1. 配置 Emby

在配置页面填写：
- Emby 服务器地址（如：`http://192.168.1.100:8096`）
- API 密钥（在 Emby 设置 → API 中获取）

### 2. 配置 MoviePilot（可选）

- MoviePilot 服务器地址（如：`http://192.168.1.100:3000`）
- 用户名
- 密码

### 3. 开始检测

点击"开始检测"按钮，等待分析完成（约 2 分钟）。

### 4. 推送下载

点击剧集旁的"⬇️"按钮，推送缺失剧集到 MoviePilot。

## API 接口

### 获取检测结果
```bash
GET /api/cards
```

### 推送下载
```bash
POST /api/download
Content-Type: application/json

{
  "series_id": "12345",
  "series_name": "剧名",
  "season": 1,
  "episodes": [1, 2, 3]
}
```

### 获取下载历史
```bash
GET /api/download/history
```

## 技术栈

- **后端**: Python 3.11 + FastAPI
- **前端**: 原生 HTML + JavaScript
- **数据库**: SQLite
- **API**: Emby API + MoviePilot API

## 项目结构

```
emby-missing-episode-detector/
├── app/
│   ├── config_manager.py    # 配置管理
│   ├── database.py          # 数据库操作
│   ├── detector.py          # 缺集检测逻辑
│   ├── emby_client.py       # Emby API 客户端
│   ├── moviepilot_client.py # MoviePilot API 客户端
│   └── scheduler.py         # 定时任务调度
├── config/
│   └── settings.json        # 配置文件（不提交）
├── data/
│   └── emby_detector.db     # 数据库文件（不提交）
├── static/
│   └── index.html           # Web 界面
├── logs/                    # 日志目录
├── main.py                  # 主程序入口
├── run.sh                   # 启动脚本
└── README.md                # 说明文档
```

## 注意事项

1. **配置文件** - `config/settings.json` 包含敏感信息，已添加到 `.gitignore`
2. **数据库** - `data/*.db` 包含检测历史，已添加到 `.gitignore`
3. **日志** - `logs/*.log` 包含运行日志，已添加到 `.gitignore`

## License

MIT License
