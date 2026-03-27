"""
企业微信资源搜索服务
通过 PanSou API 搜索网盘资源，支持分页浏览
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger

PAGE_SIZE = 5


class WeComSearchService:
    """企业微信资源搜索服务"""

    SESSION_TTL_SECONDS = 30 * 60

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def handle_text_message(
        self,
        user_id: str,
        content: str,
        pansou_client: Any,
        wecom_client: Any = None,
    ) -> str:
        text = " ".join((content or "").strip().split())
        if not text:
            return "请发送关键词搜索网盘资源，例如：遮天"

        # 分页导航命令
        nav = self._parse_nav(text)
        if nav is not None:
            return self._turn_page(user_id, nav)

        # 其他文本视为新搜索
        return self._do_search(user_id, text, pansou_client)

    # ── 搜索 ──────────────────────────────────────────────────────────────

    def _do_search(self, user_id: str, keyword: str, pansou_client: Any) -> str:
        if pansou_client is None:
            return "PanSou 未配置，无法搜索资源。"

        try:
            data = pansou_client.search(keyword)
        except Exception as exc:
            logger.error(f"PanSou 搜索失败: {exc}")
            return f"搜索失败：{exc}"

        # 将 merged_by_type 展平为有序列表
        merged: Dict[str, List] = data.get("merged_by_type") or {}
        items: List[Dict[str, Any]] = []
        for pan_type, links in merged.items():
            for link in links:
                items.append({**link, "_pan_type": pan_type})

        total = len(items)
        if total == 0:
            return f'没有找到"{keyword}"的相关资源。'

        self._set_session(user_id, {"keyword": keyword, "items": items, "page": 1})
        return self._format_page(keyword, items, page=1, total=total)

    # ── 翻页 ──────────────────────────────────────────────────────────────

    def _turn_page(self, user_id: str, target_page: int) -> str:
        session = self._get_session(user_id)
        if not session:
            return "没有进行中的搜索，请先发送关键词。"

        keyword = session.get("keyword", "")
        items: List[Dict[str, Any]] = session.get("items", [])
        total = len(items)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

        if target_page == -1:
            page = session.get("page", 1) + 1
        elif target_page == -2:
            page = session.get("page", 1) - 1
        else:
            page = target_page

        page = max(1, min(page, total_pages))
        self._set_session(user_id, {**session, "page": page})
        return self._format_page(keyword, items, page=page, total=total)

    # ── 格式化 ────────────────────────────────────────────────────────────

    def _format_page(
        self, keyword: str, items: List[Dict[str, Any]], page: int, total: int
    ) -> str:
        from app.pansou_client import PanSouClient

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        start = (page - 1) * PAGE_SIZE
        page_items = items[start: start + PAGE_SIZE]

        lines = [f'🔍 "{keyword}" 搜索结果（共 {total} 条，第 {page}/{total_pages} 页）', ""]

        for idx, item in enumerate(page_items, start=start + 1):
            pan_type = item.get("_pan_type", "")
            pan_name = PanSouClient.pan_display_name(pan_type)
            note = (item.get("note") or item.get("work_title") or "").strip()
            url = item.get("url", "")
            password = (item.get("password") or "").strip()

            title_line = f"{idx}. {note} [{pan_name}]" if note else f"{idx}. [{pan_name}]"
            lines.append(title_line)
            if url:
                lines.append(f"   🔗 {url}")
            if password:
                lines.append(f"   🔑 {password}")
            lines.append("")

        # 页脚导航提示
        nav_hints = []
        if page > 1:
            nav_hints.append("「上一页」")
        if page < total_pages:
            nav_hints.append("「下一页」")
        if nav_hints:
            lines.append(f"回复 {'或'.join(nav_hints)} 翻页，或发送新关键词重新搜索")
        else:
            lines.append("发送新关键词重新搜索")

        return "\n".join(lines)

    # ── 导航解析 ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_nav(text: str) -> Optional[int]:
        """返回目标页码；-1=下一页，-2=上一页；None=不是导航命令"""
        t = text.strip()
        if t in {"下一页", "next", "下页"}:
            return -1
        if t in {"上一页", "prev", "上页"}:
            return -2
        m = re.match(r"^第\s*(\d+)\s*页$", t)
        if m:
            return int(m.group(1))
        return None

    # ── Session ───────────────────────────────────────────────────────────

    def _set_session(self, user_id: str, payload: Dict[str, Any]):
        with self._lock:
            self._cleanup_expired_locked()
            self._sessions[user_id] = {**payload, "_updated_at": time.time()}

    def _get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.get(user_id)
            if session:
                session["_updated_at"] = time.time()
                return {k: v for k, v in session.items() if k != "_updated_at"}
        return None

    def _cleanup_expired_locked(self):
        now = time.time()
        expired = [
            uid
            for uid, s in self._sessions.items()
            if now - s.get("_updated_at", now) > self.SESSION_TTL_SECONDS
        ]
        for uid in expired:
            self._sessions.pop(uid, None)
