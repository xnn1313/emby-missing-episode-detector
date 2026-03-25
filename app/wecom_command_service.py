"""
企业微信命令处理
复用 TMDB 与 HDHive 现有能力，支持搜剧、查资源、解锁
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger


class WeComCommandService:
    """企业微信命令服务"""

    SESSION_TTL_SECONDS = 30 * 60

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def handle_text_message(
        self,
        user_id: str,
        content: str,
        tmdb_client: Any,
        hdhive_client: Any,
        db: Any,
        config_manager: Any,
    ) -> str:
        text = " ".join((content or "").strip().split())
        if not text:
            return self._help_text()

        if text in {"帮助", "help", "菜单", "?"}:
            return self._help_text()

        if text == "重置":
            self._clear_session(user_id, db=db)
            return "会话已重置。\n发送“搜索 剧名”重新开始。"

        search_match = re.match(r"^(搜索|搜剧|search)\s+(.+)$", text, flags=re.IGNORECASE)
        if search_match:
            return self._search_series(
                user_id=user_id,
                keyword=search_match.group(2).strip(),
                tmdb_client=tmdb_client,
                db=db,
            )

        resource_match = re.match(r"^(资源|res)\s+(\d+)$", text, flags=re.IGNORECASE)
        if resource_match:
            return self._search_resources(
                user_id=user_id,
                index=int(resource_match.group(2)),
                hdhive_client=hdhive_client,
                config_manager=config_manager,
                db=db,
            )

        unlock_match = re.match(r"^(解锁|unlock)\s+(\d+)$", text, flags=re.IGNORECASE)
        if unlock_match:
            return self._unlock_resource(
                user_id=user_id,
                index=int(unlock_match.group(2)),
                hdhive_client=hdhive_client,
                db=db,
                config_manager=config_manager,
            )

        if text == "历史":
            return self._latest_history(db)

        return (
            "无法识别命令。\n\n"
            f"{self._help_text()}"
        )

    def _search_series(self, user_id: str, keyword: str, tmdb_client: Any, db: Any = None) -> str:
        if tmdb_client is None:
            return "TMDB 未配置，无法按剧名搜索。请先在系统里配置 TMDB API Key。"

        try:
            candidates = tmdb_client.search_tv_series_candidates(keyword, limit=5)
        except Exception as exc:
            logger.error(f"企业微信搜剧失败: {exc}")
            return f"搜剧失败：{exc}"

        if not candidates:
            return f"没有找到“{keyword}”的剧集候选。"

        self._set_session(
            user_id,
            {
                "tmdb_results": candidates,
                "resource_results": [],
                "last_keyword": keyword,
                "last_action": "search",
            },
            db=db,
        )

        lines = [f"找到 {len(candidates)} 个候选："]
        for idx, item in enumerate(candidates, start=1):
            air_date = item.get("first_air_date") or ""
            title = item.get("name") or item.get("original_name") or "未知剧名"
            tmdb_id = item.get("id")
            lines.append(f"{idx}. {title} {f'({air_date})' if air_date else ''} [TMDB:{tmdb_id}]")

        lines.append("")
        lines.append("回复“资源 序号”查看 HDHive 资源，例如：资源 1")
        return "\n".join(lines)

    def _search_resources(
        self,
        user_id: str,
        index: int,
        hdhive_client: Any,
        config_manager: Any,
        db: Any = None,
    ) -> str:
        if hdhive_client is None:
            return "HDHive 未配置，无法查询资源。"

        session = self._get_session(user_id, db=db)
        tmdb_results = session.get("tmdb_results", [])
        if not tmdb_results:
            return "没有可用的搜剧结果。请先发送“搜索 剧名”。"

        if index < 1 or index > len(tmdb_results):
            return f"序号无效，请输入 1 到 {len(tmdb_results)}。"

        target = tmdb_results[index - 1]
        prefer_115 = True
        if config_manager is not None:
            prefer_115 = config_manager.get_hdhive_config().get("settings", {}).get("prefer_115", True)

        try:
            resources = hdhive_client.search_tv_resources(
                tmdb_id=str(target.get("id")),
                prefer_115=prefer_115,
            )
        except Exception as exc:
            logger.error(f"企业微信查询资源失败: {exc}")
            return f"查询资源失败：{exc}"

        if not resources:
            return f"没有找到“{target.get('name', '未知剧名')}”的可用资源。"

        resource_results: List[Dict[str, Any]] = []
        for item in resources[:8]:
            normalized_pan_type = self._normalize_pan_type(
                item.get("pan_type"),
                item.get("title") or "",
            )
            resource_results.append(
                {
                    "slug": item.get("slug"),
                    "title": item.get("title") or "未知资源",
                    "unlock_points": item.get("unlock_points") or 0,
                    "is_unlocked": item.get("is_unlocked", False),
                    "video_resolution": item.get("video_resolution", []),
                    "source": item.get("source", []),
                    "pan_type": normalized_pan_type,
                    "tmdb_id": str(target.get("id")),
                    "series_name": target.get("name") or target.get("original_name") or "",
                }
            )

        self._set_session(
            user_id,
            {
                **session,
                "resource_results": resource_results,
                "selected_tmdb": target,
                "last_action": "resources",
            },
            db=db,
        )

        max_points = 0
        if config_manager is not None:
            max_points = config_manager.get_hdhive_config().get("settings", {}).get("max_points_per_unlock", 0)

        lines = [f"{target.get('name', '未知剧名')} 的资源如下："]
        for idx, item in enumerate(resource_results, start=1):
            resolutions = "/".join(item.get("video_resolution") or []) or "-"
            sources = "/".join(item.get("source") or []) or "-"
            points = item.get("unlock_points", 0)
            extra = " 已解锁" if item.get("is_unlocked") else ""
            if max_points and points > max_points:
                extra += " 超过积分上限"
            
            pan_type = (item.get("pan_type") or "").strip()
            pan_name = self._pan_display_name(pan_type)
            pan_badge = f"[{pan_name}]" if pan_name else "[网盘未知]"
            
            lines.append(
                f"{idx}. {item['title']} {pan_badge}\n"
                f"积分:{points} 网盘:{pan_name or '未知'} 分辨率:{resolutions} 来源:{sources}{extra}"
            )

        lines.append("")
        lines.append("回复“解锁 序号”获取链接，例如：解锁 1")
        return "\n".join(lines)

    def build_news_articles(self, user_id: str, db: Any = None) -> List[Dict[str, str]]:
        session = self._get_session(user_id, db=db)
        action = session.get("last_action")
        articles: List[Dict[str, str]] = []

        def poster_url(path: str) -> str:
            p = (path or "").strip()
            if not p:
                return ""
            if p.startswith("http://") or p.startswith("https://"):
                return p
            return f"https://image.tmdb.org/t/p/w500{p}"

        if action == "search":
            candidates = session.get("tmdb_results") or []
            for item in candidates[:6]:
                title = item.get("name") or item.get("original_name") or "未知剧名"
                air_date = item.get("first_air_date") or ""
                year = air_date[:4] if air_date else ""
                pic = poster_url(item.get("poster_path") or "")
                if not pic:
                    continue
                tmdb_id = str(item.get("id") or "")
                articles.append(
                    {
                        "title": f"{title}{f' ({year})' if year else ''}",
                        "description": f"TMDB {tmdb_id}" if tmdb_id else "",
                        "url": f"https://www.themoviedb.org/tv/{tmdb_id}" if tmdb_id else "https://www.themoviedb.org/",
                        "picurl": pic,
                    }
                )

        elif action == "resources":
            target = session.get("selected_tmdb") or {}
            title = target.get("name") or target.get("original_name") or "未知剧名"
            air_date = target.get("first_air_date") or ""
            year = air_date[:4] if air_date else ""
            pic = poster_url(target.get("poster_path") or "")
            tmdb_id = str(target.get("id") or "")
            if pic:
                articles.append(
                    {
                        "title": f"{title}{f' ({year})' if year else ''}",
                        "description": f"TMDB {tmdb_id}" if tmdb_id else "",
                        "url": f"https://www.themoviedb.org/tv/{tmdb_id}" if tmdb_id else "https://www.themoviedb.org/",
                        "picurl": pic,
                    }
                )

        return articles

    def _unlock_resource(self, user_id: str, index: int, hdhive_client: Any, db: Any, config_manager: Any) -> str:
        if hdhive_client is None:
            return "HDHive 未配置，无法解锁资源。"

        session = self._get_session(user_id, db=db)
        resource_results = session.get("resource_results", [])
        if not resource_results:
            return "没有可用的资源列表。请先发送“搜索 剧名”，再发送“资源 序号”。"

        if index < 1 or index > len(resource_results):
            return f"序号无效，请输入 1 到 {len(resource_results)}。"

        target = resource_results[index - 1]
        points = int(target.get("unlock_points", 0) or 0)

        max_points = 0
        if config_manager is not None:
            max_points = config_manager.get_hdhive_config().get("settings", {}).get("max_points_per_unlock", 0)
        if max_points and points > max_points:
            return f"该资源需要 {points} 积分，超过当前限制 {max_points}，已阻止解锁。"

        try:
            result = hdhive_client.unlock_resource(target["slug"])
        except Exception as exc:
            logger.error(f"企业微信解锁失败: {exc}")
            return f"解锁失败：{exc}"

        link = result.get("full_url") or result.get("url") or ""
        access_code = result.get("access_code", "")
        if link and access_code and "提取码" not in link and "pwd=" not in link:
            link = f"{link} 提取码: {access_code}"

        if db is not None and link:
            try:
                db.save_hdhive_unlock(
                    slug=target["slug"],
                    url=link,
                    access_code=access_code,
                    tmdb_id=target.get("tmdb_id"),
                    series_name=target.get("series_name"),
                    title=target.get("title"),
                    points_spent=int(result.get("points_spent", points) or points),
                )
            except Exception as exc:
                logger.warning(f"保存企业微信解锁记录失败: {exc}")

        status_text = "已拥有该资源" if result.get("already_owned") else "解锁成功"
        pan_type = (target.get("pan_type") or "").strip()
        lines = [
            status_text,
            f"剧集: {target.get('series_name') or '未知'}",
            f"资源: {target.get('title') or '未知'}",
            f"网盘: {self._pan_display_name(pan_type) or '未知'}",
        ]
        if link:
            lines.append(f"链接: {link}")
        if access_code and "提取码" not in link:
            lines.append(f"提取码: {access_code}")

        spent = result.get("points_spent")
        if spent is None:
            spent = points
        lines.append(f"积分消耗: {spent}")
        return "\n".join(lines)

    def _latest_history(self, db: Any) -> str:
        if db is None:
            return "数据库未初始化，无法查看解锁历史。"

        try:
            records = db.get_hdhive_unlocks(limit=5)
        except Exception as exc:
            logger.error(f"获取企业微信解锁历史失败: {exc}")
            return f"读取历史失败：{exc}"

        if not records:
            return "暂无解锁历史。"

        lines = ["最近 5 条解锁记录："]
        for idx, item in enumerate(records, start=1):
            title = item.get("title") or item.get("series_name") or item.get("slug") or "未知"
            unlocked_at = item.get("unlocked_at") or "-"
            lines.append(f"{idx}. {title} | {unlocked_at}")
        return "\n".join(lines)

    def _set_session(self, user_id: str, payload: Dict[str, Any], db: Any = None):
        with self._lock:
            self._cleanup_expired_locked()
            session = {
                **payload,
                "updated_at": time.time(),
            }
            self._sessions[user_id] = session

        if db is not None:
            try:
                db.save_wecom_session(user_id, payload)
            except Exception as exc:
                logger.warning(f"保存企业微信会话失败: {exc}")

    def _get_session(self, user_id: str, db: Any = None) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.get(user_id)
            if session:
                session["updated_at"] = time.time()
                payload = {key: value for key, value in session.items() if key != "updated_at"}
            else:
                payload = None

        if payload is not None:
            if db is not None:
                try:
                    db.save_wecom_session(user_id, payload)
                except Exception as exc:
                    logger.warning(f"刷新企业微信会话失败: {exc}")
            return dict(payload)

        if db is None:
            return {}

        try:
            payload = db.get_wecom_session(user_id, self.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.warning(f"读取企业微信会话失败: {exc}")
            return {}

        if not payload:
            return {}

        with self._lock:
            self._sessions[user_id] = {
                **payload,
                "updated_at": time.time(),
            }

        return dict(payload)

    def _clear_session(self, user_id: str, db: Any = None):
        with self._lock:
            self._sessions.pop(user_id, None)

        if db is not None:
            try:
                db.delete_wecom_session(user_id)
            except Exception as exc:
                logger.warning(f"删除企业微信会话失败: {exc}")

    def _cleanup_expired_locked(self):
        now = time.time()
        expired = [
            user_id
            for user_id, payload in self._sessions.items()
            if now - payload.get("updated_at", now) > self.SESSION_TTL_SECONDS
        ]
        for user_id in expired:
            self._sessions.pop(user_id, None)

    @staticmethod
    def _help_text() -> str:
        return (
            "可用命令：\n"
            "1. 搜索 剧名\n"
            "2. 资源 序号\n"
            "3. 解锁 序号\n"
            "4. 历史\n"
            "5. 重置"
        )

    @staticmethod
    def _pan_display_name(pan_type: str) -> str:
        normalized = (pan_type or "").strip().lower()
        if normalized in {"115"}:
            return "115"
        if normalized in {"ali", "aliyun", "alipan"}:
            return "阿里云盘"
        if normalized in {"quark"}:
            return "夸克"
        if normalized in {"baidu", "bd"}:
            return "百度网盘"
        if normalized in {"xunlei", "thunder"}:
            return "迅雷"
        return pan_type.strip()

    @staticmethod
    def _normalize_pan_type(pan_type: Any, title: str) -> str:
        raw = str(pan_type or "").strip()
        normalized = raw.lower()
        if normalized in {"115"}:
            return "115"
        if normalized in {"ali", "aliyun", "alipan"}:
            return "ali"
        if normalized in {"quark"}:
            return "quark"
        if normalized in {"baidu", "bd"}:
            return "baidu"
        if normalized in {"xunlei", "thunder"}:
            return "xunlei"

        text = (title or "").strip().lower()
        if "115" in text:
            return "115"
        if "阿里" in title or "aliyun" in text or "alipan" in text:
            return "ali"
        if "夸克" in title or "quark" in text:
            return "quark"
        if "百度" in title or "baidu" in text:
            return "baidu"
        if "迅雷" in title or "xunlei" in text or "thunder" in text:
            return "xunlei"
        return raw
