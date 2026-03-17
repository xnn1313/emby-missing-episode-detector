✅ **TMDB API Key 保存问题已修复！**

## 问题原因
前端保存配置时发送的数据结构不正确：
- **前端发送**：`tmdb: { api_key: "xxx" }`（嵌套结构）
- **后端期望**：`tmdb_api_key: "xxx"`（扁平结构）

导致 TMDB API Key 没有被正确保存到后端。

## 修复内容
修改前端 `saveConfig` 函数，将 TMDB 配置改为扁平结构：
```javascript
const config = {
    host: embyHost,
    api_key: embyApiKey,
    tmdb_api_key: tmdbKey,  // 改为扁平结构
    moviepilot: { ... }
};
```

## 测试步骤
1. 刷新页面
2. 进入**配置页面**
3. 填入 TMDB API Key
4. 点击"保存配置"
5. 刷新页面或重新进入配置页面
6. TMDB API Key 应该还在（显示为 ••••••••）

## 验证命令
```bash
# 查看配置文件
cat /root/.openclaw/workspace/emby-missing-episode-detector/config/settings.json | python3 -m json.tool | grep -A3 tmdb

# 测试 TMDB API
curl -s "http://localhost:8080/api/tmdb/search?name=万界仙踪"
```

## 注意事项
- 配置文件中的 TMDB API Key 会明文存储
- 前端显示时会显示为密码框（••••••）
- 刷新页面后配置应该保持存在
