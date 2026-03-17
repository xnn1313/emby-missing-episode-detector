# HDHive 搜索问题修复

## 问题
用户反馈"万界仙踪"在 HDHive 上可以搜到，但系统提示"无法获取 TMDB ID"。

## 根本原因
1. TMDB API Key 未配置（`config/settings.json` 中 `tmdb.api_key` 为空）
2. 前端依赖 TMDB API 获取 TMDB ID，然后用 TMDB ID 搜索 HDHive
3. 没有 TMDB API Key 时，无法获取 TMDB ID，导致 HDHive 搜索失败

## 解决方案

### 方案 1：配置 TMDB API Key（推荐）
1. 访问 https://www.themoviedb.org/settings/api 申请 API Key
2. 在系统配置页面填入 TMDB API Key
3. 保存配置后重试

### 方案 2：HDHive 直接按名称搜索（待实现）
修改 HDHive 客户端，支持直接按剧集名称搜索，不依赖 TMDB ID。

### 方案 3：手动输入 TMDB ID（临时方案）
在错误提示中提供手动输入 TMDB ID 的选项。

## 当前状态
- ✅ 前端已修复错误提示，显示更详细的失败原因
- ⚠️ TMDB API Key 需要用户自行配置
- 🔄 HDHive 按名称搜索功能待开发

## 用户操作指引
1. 打开系统配置页面
2. 找到 "TMDB API Key" 配置项
3. 填入从 TMDB 官网申请的 API Key
4. 保存配置
5. 重新点击"查询 HDHive"按钮

## API Key 申请地址
- TMDB: https://www.themoviedb.org/settings/api
- 免费套餐足够使用
