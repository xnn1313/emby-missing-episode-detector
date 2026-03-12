# Emby 缺集检测系统 - MoviePilot 集成使用指南

## 📋 功能概述

本系统支持将 Emby 媒体库中的缺失剧集自动推送到 MoviePilot 进行下载，实现一站式缺集检测和自动补全。

---

## ⚙️ 配置步骤

### 1. 配置 MoviePilot

1. 打开 Web 界面：`http://192.168.31.20:8080`
2. 点击 **"配置"** 标签页
3. 找到 **"🎬 MoviePilot 配置"** 区域
4. 勾选 **"启用 MoviePilot 自动下载"**
5. 填写配置信息：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| MoviePilot 服务器地址 | MoviePilot 服务地址 | `http://192.168.1.100:3000` |
| API 密钥 | MoviePilot API 密钥 | 在 MoviePilot 设置中获取 |
| 自动下载缺失剧集 | 是否自动推送 | 勾选 |
| 下载保存路径 | 可选，指定保存位置 | `/downloads/tv` |

6. 点击 **"保存配置"**

### 2. 获取 MoviePilot API 密钥

1. 登录 MoviePilot Web 界面
2. 进入 **设置** → **API**
3. 点击 **"生成 API 密钥"** 或复制现有密钥
4. 粘贴到配置页面

---

## 🚀 使用流程

### 方式一：手动推送下载

1. **开始检测**
   - 在仪表盘点击 **"开始检测"**
   - 系统扫描 Emby 媒体库，识别缺失剧集

2. **推送下载**
   - 在列表中找到要下载的剧集
   - 点击 **"⬇️ 下载"** 按钮
   - 系统自动推送到 MoviePilot

3. **查看进度**
   - 下载进度列显示状态：
     - ⏳ 待下载
     - ⬇️ 下载中
     - ✅ 已完成
     - ❌ 失败

### 方式二：自动下载（开发中）

启用后，检测到的缺失剧集自动推送到 MoviePilot。

---

## 📊 下载状态说明

| 状态 | 图标 | 说明 |
|------|------|------|
| 待下载 | ⏳ | 已记录，等待推送 |
| 下载中 | ⬇️ | MoviePilot 正在下载 |
| 已完成 | ✅ | 下载完成，已入库 |
| 失败 | ❌ | 下载失败，点击重试 |

---

## 🔌 API 接口

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

**响应：**
```json
{
  "status": "success",
  "message": "已推送 剧名 S1 到 MoviePilot",
  "subscribe_id": "abc123",
  "record_id": 1
}
```

### 获取下载历史

```bash
GET /api/download/history?status=pending&limit=100
```

**参数：**
- `status` - 状态过滤（pending/downloading/completed/failed）
- `limit` - 返回记录数限制

### 获取剧集下载状态

```bash
GET /api/download/status/{series_id}
```

---

## 📁 配置文件

配置保存在：`config/settings.json`

```json
{
  "emby": {
    "host": "http://emby2.anhh5k.top:8888",
    "api_key": "xxx"
  },
  "moviepilot": {
    "host": "http://192.168.1.100:3000",
    "api_key": "xxx",
    "enabled": true,
    "auto_download": true,
    "download_path": "/downloads/tv"
  }
}
```

---

## 🗄️ 数据库

下载历史保存在：`data/emby_detector.db`

**表名：** `download_history`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| series_id | TEXT | 剧集 ID |
| series_name | TEXT | 剧集名称 |
| season_number | INTEGER | 季数 |
| episode_numbers | TEXT | 缺失集数（JSON） |
| moviepilot_task_id | TEXT | MoviePilot 任务 ID |
| status | TEXT | 状态 |
| pushed_at | TIMESTAMP | 推送时间 |
| completed_at | TIMESTAMP | 完成时间 |

---

## ❓ 常见问题

### Q: 点击"下载"按钮没反应？
A: 检查：
1. MoviePilot 配置是否启用
2. 服务器地址和 API 密钥是否正确
3. 浏览器控制台是否有错误

### Q: 下载进度一直显示"待下载"？
A: 可能原因：
1. MoviePilot 服务不可达
2. API 密钥无效
3. MoviePilot 订阅失败

### Q: 如何重试失败的下载？
A: 再次点击"⬇️ 下载"按钮即可重新推送。

---

## 📝 更新日志

### v0.2.0 (2026-03-12)
- ✅ 新增 MoviePilot 客户端模块
- ✅ 支持推送缺失剧集到 MoviePilot
- ✅ 下载历史记录和进度追踪
- ✅ UI 配置页面支持 MoviePilot 配置
- ✅ 列表展示下载进度

### v0.1.0 (2026-03-11)
- 初始版本发布
- Emby 缺集检测
- 海报墙/列表视图

---

## 📞 技术支持

遇到问题请查看日志：
- 应用日志：`/tmp/emby-monitor.log`
- 数据库：`data/emby_detector.db`
