# PanSou API 文档

**服务地址**: `http://47.108.129.71:57081`

---

## 📋 接口总览

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/search` | GET/POST | 搜索资源 |
| `/api/health` | GET | 健康检查 |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/verify` | POST | 验证 Token |
| `/api/auth/logout` | POST | 登出 |

---

## 🔍 1. 搜索 API

### 接口信息
- **路径**: `/api/search`
- **方法**: GET / POST
- **描述**: 强大的网盘资源搜索接口

### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `kw` | string | ✅ 是 | 搜索关键词 |
| `channels` | string[] | ❌ 否 | 搜索的频道列表，不提供则使用默认配置 |
| `conc` | number | ❌ 否 | 并发搜索数量，不提供则自动设置 |
| `refresh` | boolean | ❌ 否 | 强制刷新，不使用缓存 |
| `res` | string | ❌ 否 | 结果类型：`all` / `results` / `merge`，默认 `merge` |
| `src` | string | ❌ 否 | 数据来源：`all` / `tg` / `plugin`，默认 `all` |
| `plugins` | string[] | ❌ 否 | 指定搜索的插件列表 |
| `cloud_types` | string[] | ❌ 否 | 指定返回的网盘类型列表 |
| `ext` | object | ❌ 否 | 扩展参数，传递给插件的自定义参数 |
| `filter` | object | ❌ 否 | 过滤配置（见下方说明） |

### 过滤配置 (filter)

```json
{
  "include": ["高码", "hdr"],    // 包含关键词列表 (OR 关系)
  "exclude": ["预告", "抢先"]    // 排除关键词列表 (OR 关系)
}
```

- **include**: 结果中至少包含一个关键词
- **exclude**: 结果中包含任意一个关键词就排除

### 请求示例

#### POST 请求
```bash
curl -X POST http://47.108.129.71:57081/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "kw": "遮天",
    "channels": ["tgsearchers4", "Aliyun_4K_Movies"],
    "plugins": ["alipan", "quark"],
    "res": "merge",
    "src": "all",
    "cloud_types": ["aliyun", "quark"],
    "filter": {
      "include": ["高码", "hdr"],
      "exclude": ["预告"]
    }
  }'
```

#### GET 请求
```bash
curl -X GET "http://47.108.129.71:57081/api/search?kw=遮天&res=merge&src=all"
```

### 响应示例

```json
{
  "total": 156,
  "results": [
    {
      "message_id": "12345",
      "unique_id": "uuid-xxx",
      "channel": "tgsearchers4",
      "datetime": "2026-03-27T10:00:00Z",
      "title": "遮天 全集",
      "content": "资源描述...",
      "links": [
        {
          "type": "aliyun",
          "url": "https://www.aliyundrive.com/s/xxx",
          "password": "abc1",
          "datetime": "2026-03-27T10:00:00Z",
          "work_title": "遮天"
        }
      ],
      "tags": ["动漫", "连载"],
      "images": ["https://example.com/image1.jpg"]
    }
  ],
  "merged_by_type": {
    "aliyun": [
      {
        "url": "https://www.aliyundrive.com/s/xxx",
        "password": "abc1",
        "note": "遮天 全集",
        "datetime": "2026-03-27T10:00:00Z",
        "source": "tg:tgsearchers4",
        "images": ["https://example.com/image1.jpg"]
      }
    ]
  }
}
```

### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `total` | number | 搜索结果总数 |
| `results` | object[] | 搜索结果数组 |
| `results[].message_id` | string | TG 消息 ID |
| `results[].unique_id` | string | 全局唯一 ID |
| `results[].channel` | string | 来源频道名称 |
| `results[].datetime` | string | 发布时间 (ISO 格式) |
| `results[].title` | string | 消息标题 |
| `results[].content` | string | 消息内容 |
| `results[].links` | object[] | 包含的网盘链接数组 |
| `results[].links[].type` | string | 网盘类型 |
| `results[].links[].url` | string | 网盘链接地址 |
| `results[].links[].password` | string | 提取码/密码 |
| `results[].links[].work_title` | string | 作品标题 (用于区分同一消息中多个作品的链接) |
| `results[].tags` | string[] | 消息标签 |
| `results[].images` | string[] | 图片链接 |
| `merged_by_type` | object | 按网盘类型分组的链接 |
| `merged_by_type.{type}` | object[] | 特定网盘类型的链接数组 |
| `merged_by_type.{type}[].url` | string | 网盘链接地址 |
| `merged_by_type.{type}[].password` | string | 提取码/密码 |
| `merged_by_type.{type}[].note` | string | 资源说明/标题 |
| `merged_by_type.{type}[].datetime` | string | 发布时间 |
| `merged_by_type.{type}[].source` | string | 数据来源 (tg:频道名 或 plugin:插件名) |

---

## 🏥 2. 健康检查 API

### 接口信息
- **路径**: `/api/health`
- **方法**: GET
- **描述**: 检查服务是否正常运行

### 请求示例
```bash
curl -X GET http://47.108.129.71:57081/api/health
```

### 响应示例
```json
{
  "status": "ok",
  "plugins_enabled": true,
  "plugin_count": 70,
  "plugins": ["ddys", "erxiao", "hdr4k", ...],
  "channels": ["tgsearchers4", "Aliyun_4K_Movies", ...],
  "channels_count": 108,
  "auth_enabled": false
}
```

### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `status` | string | 服务状态，`"ok"` 表示正常 |
| `plugins_enabled` | boolean | 插件是否启用 |
| `plugin_count` | number | 可用插件数量 |
| `plugins` | string[] | 可用插件列表 |
| `channels` | string[] | 配置的频道列表 |
| `channels_count` | number | 频道数量 |
| `auth_enabled` | boolean | 是否启用认证功能（`true`=已启用，所有 API 需要 token；`false`=未启用，不需要 token） |

---

## 🔐 3. 认证 API

### 3.1 登录接口

#### 接口信息
- **路径**: `/api/auth/login`
- **方法**: POST
- **描述**: 用户登录获取 Token

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `username` | string | ✅ 是 | 用户名 |
| `password` | string | ✅ 是 | 密码 |

#### 请求示例
```bash
curl -X POST http://47.108.129.71:57081/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123"
  }'
```

#### 响应示例
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": 1234567890,
  "username": "admin"
}
```

### 3.2 验证接口

#### 接口信息
- **路径**: `/api/auth/verify`
- **方法**: POST
- **描述**: 验证 Token 是否有效
- **请求头**: `Authorization: Bearer <token>`

#### 请求示例
```bash
curl -X POST http://47.108.129.71:57081/api/auth/verify \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 响应示例 (成功)
```json
{
  "valid": true,
  "username": "admin"
}
```

#### 响应示例 (失败)
```json
{
  "error": "未授权：令牌无效或已过期",
  "code": "AUTH_TOKEN_INVALID"
}
```

### 3.3 登出接口

#### 接口信息
- **路径**: `/api/auth/logout`
- **方法**: POST
- **描述**: 退出登录 (JWT 无状态，客户端删除 token 即可)

#### 请求示例
```bash
curl -X POST http://47.108.129.71:57081/api/auth/logout
```

#### 响应示例
```json
{
  "message": "退出成功"
}
```

---

## 🌐 4. 支持的网盘类型

| ID | 名称 | 图标 |
|----|------|------|
| `baidu` | 百度网盘 | 🔵 |
| `aliyun` | 阿里云盘 | 🟠 |
| `quark` | 夸克网盘 | 🟡 |
| `tianyi` | 天翼云盘 | 🔴 |
| `uc` | UC 网盘 | 🟢 |
| `mobile` | 移动云盘 | 🔵 |
| `115` | 115 网盘 | 🟣 |
| `pikpak` | PikPak | 🌈 |
| `xunlei` | 迅雷网盘 | ⚡ |
| `123` | 123 网盘 | 🎯 |
| `magnet` | 磁力链接 | 🧲 |
| `ed2k` | 电驴链接 | 🔗 |

---

## ⚡ 5. 性能特性

- 🚀 **高性能并发搜索**：支持同时搜索多个 TG 频道和插件
- 🧠 **智能排序算法**：基于插件等级、时间新鲜度和关键词匹配
- 💾 **分片缓存机制**：内存 + 磁盘双重缓存提升响应速度
- 🔄 **异步插件系统**："尽快响应，持续处理"的搜索模式
- 📊 **自动网盘类型识别**和分类展示

---

## 🛡️ 6. 错误处理

| 状态码 | 描述 |
|--------|------|
| `400` | 参数错误 - 关键词不能为空或参数格式错误 |
| `500` | 服务器错误 - 服务内部错误 |
| `429` | 请求过频 - 超过限流阈值 |
| `401` | 未授权 - 认证失败 (启用认证时) |

---

## 💡 7. 使用建议

### 🎯 关键词优化
使用准确的关键词能获得更好的搜索结果

### ⚡ 缓存利用
相同搜索会使用缓存，设置 `refresh=true` 可强制获取最新数据

### 🔄 异步模式
插件搜索采用异步模式，可能会有延迟返回更多结果

### 🎛️ 参数调优
根据需要调整并发数、网盘类型等参数优化搜索效果

---

## 📌 8. 配置说明

### 查看可用配置
```bash
curl http://47.108.129.71:57081/api/health
```

返回结果中包含:
- `channels`: 可用的 TG 频道列表
- `plugins`: 可用的搜索插件列表

### 配置来源
更多信息请参考：[GitHub Issues #4](https://github.com/fish2018/pansou/issues/4)

---

**文档更新时间**: 2026-03-27  
**服务版本**: 最新版
