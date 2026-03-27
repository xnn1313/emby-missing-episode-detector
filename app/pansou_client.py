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
        """搜索网盘资源，返回原始响应 dict"""
        payload: Dict[str, Any] = {"kw": kw, "res": "merge", "src": "all"}
        if cloud_types:
            payload["cloud_types"] = cloud_types

        try:
            resp = self.http.post(
                f"{self.base_url}/api/search",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"PanSou 搜索失败: kw={kw}, error={exc}")
            raise

    @staticmethod
    def pan_display_name(pan_type: str) -> str:
        return PAN_ICONS.get(pan_type.lower(), pan_type)
