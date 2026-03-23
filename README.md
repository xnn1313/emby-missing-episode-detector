# Emby 缺集检测系统

基于 MoviePilot 设计理念的 Emby 媒体库缺集检测工具，支持自动推送缺失剧集到 MoviePilot 自动下载。

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 功能特性

- 🔍 **自动检测** - 扫描 Emby 媒体库，识别缺失剧集
- 📊 **列表视图** - 支持排序、筛选、分页、暗黑模式
- 🚀 **MoviePilot 集成** - 一键推送缺失剧集到 MoviePilot 自动下载
- 💬 **企业微信搜剧解锁** - 在企业微信里搜索剧集、查看 HDHive 资源并回传解锁链接
- 💾 **数据持久化** - 检测结果缓存，无需重复检测
- 🎯 **智能去重** - 自动识别 Emby 重复刮削的剧集
- ⏰ **定时检测** - 支持周期性自动检测
- 📱 **响应式设计** - 支持桌面和移动端访问

---

## 快速开始

### 1. 安装依赖

```bash
cd emby-missing-episode-detector
pip3 install -r requirements.txt
```

### 2. 启动服务

```bash
# 启动服务
./run.sh start

# 查看状态
./run.sh status

# 停止服务
./run.sh stop

# 重启服务
./run.sh restart
```

默认端口：**8080**  
访问地址：`http://localhost:8080`

### 3. 配置 Emby

在 Web 界面配置页面填写：
- **Emby 服务器地址**：如 `http://192.168.1.100:8096`
- **API 密钥**：在 Emby 控制台 → 高级 → API 密钥 中创建

### 4. 配置 MoviePilot（可选）

- **MoviePilot 地址**：如 `http://192.168.1.100:3000`
- **用户名**：MoviePilot 登录用户名
- **密码**：MoviePilot 登录密码

> 💡 MoviePilot 会自动识别已存在的集数，只下载缺失的集数

### 5. 开始检测

点击"开始检测"按钮，等待分析完成（约 1-2 分钟）。

### 6. 推送下载

点击剧集旁的 **⬇️ 下载** 按钮，推送缺失剧集到 MoviePilot。

---

## 服务管理

### 启动脚本命令

| 命令 | 说明 |
|------|------|
| `./run.sh start` | 启动服务 |
| `./run.sh stop` | 停止服务 |
| `./run.sh restart` | 重启服务 |
| `./run.sh status` | 查看状态 |

### 日志查看

```bash
# 实时查看日志
tail -f logs/uvicorn.log

# 查看最近 100 行
tail -100 logs/uvicorn.log
```

### 端口占用处理

```bash
# 查看端口占用
lsof -i:8080

# 强制释放端口
fuser -k 8080/tcp

# 或重启服务
./run.sh restart
```

---

## API 接口

### 系统状态
```bash
GET /api/status
```

### 获取媒体库列表
```bash
GET /api/libraries
```

### 获取/设置配置
```bash
GET  /api/config
POST /api/config
```

### 开始检测
```bash
POST /api/detect
```

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
GET /api/download/status/{series_id}
```

### 调度器状态
```bash
GET /api/scheduler/status
```

---

## 配置说明

### 配置文件位置
`config/settings.json`

### 配置格式
```json
{
  "emby": {
    "host": "http://192.168.1.100:8096",
    "api_key": "your-api-key"
  },
  "libraries": {
    "enabled": false,
    "selected_ids": []
  },
  "tmdb": {
    "enabled": false,
    "api_key": ""
  },
  "detection": {
    "interval_minutes": 60,
    "auto_start": true
  },
  "moviepilot": {
    "host": "http://192.168.1.100:3000",
    "username": "admin",
    "password": "your-password",
    "enabled": true,
    "auto_download": true,
    "download_path": "/downloads/tv"
  },
  "wecom": {
    "enabled": false,
    "corp_id": "wwxxxxxxxxxxxxxxxx",
    "agent_id": 1000002,
    "corp_secret": "",
    "token": "",
    "encoding_aes_key": "",
    "base_url": "https://qyapi.weixin.qq.com/cgi-bin"
  }
}
```

### 企业微信命令

在企业微信自建应用中把消息回调地址配置为：

```text
http://your-server:8080/api/wecom/callback
```

需要在系统配置或 `config/settings.json` 中填写：

- `corp_id`：企业 ID
- `agent_id`：应用 AgentId
- `corp_secret`：应用 Secret，用于主动发送应用消息与校验连接
- `token`：回调 Token
- `encoding_aes_key`：回调 EncodingAESKey

应用收到文本消息后支持以下命令：

- `搜索 剧名`
- `资源 1`
- `解锁 1`
- `历史`
- `重置`

### 环境变量（可选）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `EMBY_HOST` | Emby 服务器地址 | - |
| `EMBY_API_KEY` | Emby API 密钥 | - |
| `MOVIEPILOT_HOST` | MoviePilot 地址 | - |
| `MOVIEPILOT_USERNAME` | MoviePilot 用户名 | admin |
| `MOVIEPILOT_PASSWORD` | MoviePilot 密码 | - |
| `DETECTION_INTERVAL` | 检测间隔（分钟） | 60 |

---

## 项目结构

```
emby-missing-episode-detector/
├── app/
│   ├── config_manager.py    # 配置管理
│   ├── database.py          # 数据库操作
│   ├── detector.py          # 缺集检测逻辑
│   ├── emby_client.py       # Emby API 客户端
│   ├── moviepilot_client.py # MoviePilot API 客户端
│   ├── scheduler.py         # 定时任务调度
│   └── ...
├── config/
│   └── settings.json        # 配置文件（不提交）
├── data/
│   └── emby_detector.db     # 数据库文件（不提交）
├── static/
│   └── index.html           # Web 界面
├── logs/                    # 日志目录
├── cron-progress.sh         # 定时进度汇报脚本
├── run.sh                   # 启动脚本
├── main.py                  # 主程序入口
└── README.md                # 说明文档
```

---

## 常见问题

### Q: 服务启动失败，端口被占用
**A:** 运行 `./run.sh restart` 或 `fuser -k 8080/tcp` 释放端口

### Q: MoviePilot 推送失败
**A:** 检查用户名密码是否正确，MoviePilot 需要使用登录凭证获取 Bearer Token

### Q: 检测结果不准确
**A:** 可能是 Emby 重复刮削导致，系统会自动去重，如需重新检测请清空数据库后重试

### Q: 如何修改检测间隔
**A:** 在 Web 界面配置页面修改，或编辑 `config/settings.json` 中的 `detection.interval_minutes`

---

## 注意事项

1. **敏感信息** - `config/settings.json` 包含密码等敏感信息，已添加到 `.gitignore`，不要提交到 Git
2. **数据库** - `data/*.db` 包含检测历史，已添加到 `.gitignore`
3. **日志** - `logs/*.log` 包含运行日志，已添加到 `.gitignore`
4. **备份** - 定期备份 `config/settings.json` 和 `data/emby_detector.db`

---

## 技术栈

- **后端**: Python 3.11 + FastAPI
- **前端**: 原生 HTML + JavaScript + CSS
- **数据库**: SQLite
- **API 集成**: Emby API + MoviePilot API
- **定时任务**: APScheduler

---

## 开发进度

当前进度：**97%** ✅

已完成：
- ✅ Emby 集成
- ✅ MoviePilot 集成
- ✅ Web 界面（暗黑模式）
- ✅ 配置管理
- ✅ 数据持久化
- ✅ 服务守护进程
- ✅ 定时进度汇报

---

## License

MIT License

---

**最后更新：** 2026-03-13  
**GitHub:** https://github.com/xnn1313/emby-missing-episode-detector
