# Emby 缺集检测系统 - MoviePilot 集成任务清单

创建时间：2026-03-12 10:52
优先级：P0（核心功能扩展）

---

## 🎯 功能需求

### 1. 下载按钮 + 推送 MoviePilot
**需求描述：**
- 在列表每一行添加"下载"按钮
- 点击后将缺失剧集信息推送到 MoviePilot
- MoviePilot 自动搜索并下载缺失剧集
- 记录推送历史（时间、剧集、状态）

**技术方案：**
- 新增 API：`/api/download` (POST)
- 创建 `app/moviepilot_client.py` 客户端
- 数据库记录推送历史
- UI 添加下载按钮和状态显示

**状态：** ⏳ 待开始

---

### 2. MoviePilot 配置持久化
**需求描述：**
- 支持配置 MoviePilot 地址和 API 密钥
- 配置保存到 `config/settings.json`
- UI 配置页面添加 MoviePilot 配置项

**技术方案：**
- 扩展 `FullConfig` 数据模型
- 添加 `moviepilot` 配置节点
- UI 配置页面新增表单

**状态：** ⏳ 待开始

---

### 3. 下载进度获取 + 展示
**需求描述：**
- 定时获取 MoviePilot 下载进度
- 在列表中展示下载状态（下载中/已完成/失败）
- 支持手动刷新进度

**技术方案：**
- MoviePilot API 查询下载任务
- 数据库关联下载任务 ID
- UI 新增"下载进度"列
- 定时轮询更新进度（每 5 分钟）

**状态：** ⏳ 待开始

---

## 📋 任务分解

| 任务 ID | 任务描述 | 优先级 | 状态 | 开始时间 | 完成时间 |
|--------|---------|--------|------|---------|---------|
| T001 | 创建 MoviePilot 客户端模块 | P0 | ✅ 已完成 | 10:55 | 10:58 |
| T002 | 扩展配置模型支持 MoviePilot | P0 | ✅ 已完成 | 10:58 | 11:00 |
| T003 | UI 配置页面添加 MoviePilot 配置 | P0 | ✅ 已完成 | 11:00 | 11:15 |
| T004 | 数据库添加下载历史表 | P0 | ✅ 已完成 | 11:00 | 11:03 |
| T005 | 实现推送下载 API | P0 | ✅ 已完成 | 11:03 | 11:08 |
| T006 | UI 列表添加下载按钮 | P1 | ✅ 已完成 | 11:15 | 11:20 |
| T007 | 实现下载进度获取 API | P1 | ✅ 已完成 | 11:08 | 11:10 |
| T008 | UI 列表展示下载进度 | P1 | ✅ 已完成 | 11:15 | 11:20 |
| T009 | 定时轮询下载进度 | P1 | ✅ 已完成 | 11:20 | 11:25 |
| T010 | 测试验证 + 文档更新 | P1 | ✅ 已完成 | 11:20 | 11:25 |

---

## ⏰ 定时器设置

- **检查间隔：** 10 分钟
- **汇报对象：** QQ (BA6EFF18B32E7F5930D80AD6F256A7B1)
- **汇报内容：** 任务进度表更新
- **状态：** ✅ 已启动

---

## 📦 需要创建的模块

1. `app/moviepilot_client.py` - MoviePilot API 客户端
2. `app/download_manager.py` - 下载任务管理
3. 数据库表：`download_history`
4. API 端点：
   - `POST /api/download` - 推送下载
   - `GET /api/download/status` - 获取下载状态
   - `GET /api/moviepilot/tasks` - 获取 MoviePilot 任务列表

---

## 🔌 MoviePilot API 参考

```python
# 搜索剧集
POST /api/v1/search/tv
{
    "keyword": "剧名",
    "season": 1
}

# 添加下载任务
POST /api/v1/download/add
{
    "torrent_id": "xxx",
    "save_path": "/path"
}

# 查询下载进度
GET /api/v1/download/tasks
```

---

## 📝 开发笔记

- 代码位置：`/root/.openclaw/workspace/emby-missing-episode-detector/`
- 配置中心：`app/config_manager.py`
- 数据库：`app/database.py`
- UI：`static/index.html`
