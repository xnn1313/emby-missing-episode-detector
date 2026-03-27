"""
PanSou 网盘资源搜索客户端
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

PAN_ICONS: Dict[str, str] = {
    "aliyun": "🟠阿里云盘",
    "quark": "🟡夸克网盘",
    "baidu": "🔵百度网盘",
    "115": "🟣115网盘",
    "uc": "🟢UC网盘",
    "tianyi": "🔴天翼云盘",
    "mobile": "🔵移动云盘",
    "pikpak": "🌈PikPak",
    "xunlei": "⚡迅雷网盘",
    "123": "🎯123网盘",
    "magnet": "🧲磁力链接",
    "ed2k": "🔗电驴链接",
}


class PanSouClient:
    """PanSou 搜索客户端"""

    def __init__(self, base_url: str = "http://47.108.129.71:57081", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = httpx.Client(timeout=30.0)

    def close(self):
        self.http.close()

    def _headers(self) -> Dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def search(self, kw: str, cloud_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """搜索网盘资源，返回 data 字段内容"""
        params: Dict[str, Any] = {"kw": kw, "res": "merge"}
        if cloud_types:
            params["cloud_types"] = ",".join(cloud_types)

        try:
            resp = self.http.get(
                f"{self.base_url}/api/search",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            result = resp.json()
            # PanSou API 返回格式: {"code": 0, "message": "success", "data": {...}}
            if result.get("code") == 0:
                return result.get("data", {})
            else:
                logger.error(f"PanSou API 返回错误: code={result.get('code')}, message={result.get('message')}")
                return {}
        except Exception as exc:
            logger.error(f"PanSou 搜索失败: kw={kw}, error={exc}")
            raise

    @staticmethod
    def pan_display_name(pan_type: str) -> str:
        return PAN_ICONS.get(pan_type.lower(), pan_type)
