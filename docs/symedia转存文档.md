# Symedia 115 转存 API 文档

本接口用于通过 Symedia 插件将 115 网盘的分享链接（支持带提取码的链接）自动转存到指定的 115 网盘文件夹中。

## 1. 接口信息

- **HTTP 方法**: `POST`
- **请求路径**: `[主机地址]/api/v1/plugin/cloud_helper/add_share_urls_115`
- **认证方式**: URL 参数 `token`（默认值为 `symedia`）

> **注意**: `[主机地址]` 为您部署 Symedia 服务的地址及端口，例如 `http://192.168.1.100:8095`。

---

## 2. 请求参数 (Query Parameters)

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| `token` | String | 是 | `symedia` | 用于接口调用的身份验证令牌。 |

---

## 3. 请求头 (Request Headers)

| Header | 值 | 描述 |
| :--- | :--- | :--- |
| `Content-Type` | `application/json` | 声明请求体格式为 JSON |

---

## 4. 请求体 (Request Body)

请求体需使用标准的 JSON 数组和字符串格式。

| 字段名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `urls` | Array<String> | 是 | 包含 115 分享链接的数组。支持格式：`https://115.com/s/xxx?password=yyyy` |
| `parent_id` | String | 否 | 目标文件夹的 CID。若转存至根目录请填写 `"0"`。**必须加引号**。 |

**请求体示例：**
```json
{
  "urls": [
    "[https://115.com/s/12345abcde?password=abcd](https://115.com/s/12345abcde?password=abcd)"
  ],
  "parent_id": "0"
}