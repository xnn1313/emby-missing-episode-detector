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
        wecom_client: Any = None,
    ) -> str:
        text = " ".join((content or "").strip().split())
        if not text:
            return self._help_text()

        if text in {"\u5e2e\u52a9", "help", "\u83dc\u5355", "?"}:
            return self._help_text()

        if text == "\u91cd\u7f6e":
            self._clear_session(user_id, db=db)
            return "\u4f1a\u8bdd\u5df2\u91cd\u7f6e\u3002\n\u53d1\u9001\u201c\u641c\u7d22 \u5267\u540d\u201d\u91cd\u65b0\u5f00\u59cb\u3002"

        search_match = re.match(r"^(\u641c\u7d22|\u641c\u5267|search)\s+(.+)$", text, flags=re.IGNORECASE)
        if search_match:
            return self._search_series(
                user_id=user_id,
                keyword=search_match.group(2).strip(),
                tmdb_client=tmdb_client,
                db=db,
                wecom_client=wecom_client,
            )

        resource_match = re.match(r"^(\u8d44\u6e90|res)\s+(\d+)$", text, flags=re.IGNORECASE)
        if resource_match:
            return self._search_resources(
                user_id=user_id,
                index=int(resource_match.group(2)),
                hdhive_client=hdhive_client,
                config_manager=config_manager,
                db=db,
            )

        unlock_match = re.match(r"^(\u89e3\u9501|unlock)\s+(\d+)$", text, flags=re.IGNORECASE)
        if unlock_match:
            return self._unlock_resource(
                user_id=user_id,
                index=int(unlock_match.group(2)),
                hdhive_client=hdhive_client,
                db=db,
                config_manager=config_manager,
            )

        if text == "\u5386\u53f2":
            return self._latest_history(db)

        return (
            "\u65e0\u6cd5\u8bc6\u522b\u547d\u4ee4\u3002\n\n"
            f"{self._help_text()}"
        )

    def _search_series(self, user_id: str, keyword: str, tmdb_client: Any, db: Any = None, wecom_client: Any = None) -> str:
        if tmdb_client is None:
            return "TMDB \u672a\u914d\u7f6e\uff0c\u65e0\u6cd5\u6309\u5267\u540d\u641c\u7d22\u3002\u8bf7\u5148\u5728\u7cfb\u7edf\u91cc\u914d\u7f6e TMDB API Key\u3002"

        try:
            candidates = tmdb_client.search_tv_series_candidates(keyword, limit=5)
        except Exception as exc:
            logger.error(f"\u4f01\u4e1a\u5fae\u4fe1\u641c\u5267\u5931\u8d25: {exc}")
            return f"\u641c\u5267\u5931\u8d25\uff1a{exc}"

        if not candidates:
            return f"\u6ca1\u6709\u627e\u5230\u201c{keyword}\u201d\u7684\u5267\u96c6\u5019\u9009\u3002"

        self._set_session(
            user_id,
            {
                "tmdb_results": candidates,
                "resource_results": [],
                "last_keyword": keyword,
            },
            db=db,
        )

        # 构建图文消息（企业微信 mpnews 必须有 thumb_media_id 才能显示图片）
        # 先上传第一张海报获取 media_id
        first_media_id = None
        if candidates and candidates[0].get("poster_path") and wecom_client is not None:
            try:
                first_poster_url = f"https://image.tmdb.org/t/p/w342{candidates[0]['poster_path']}"
                first_media_id = wecom_client.upload_media_image_url(first_poster_url)
                if first_media_id:
                    logger.info(f"企业微信海报上传成功：media_id={first_media_id}")
            except Exception as exc:
                logger.warning(f"企业微信上传海报失败：{exc}")
        
        # 如果有 media_id，发送图文消息
        if first_media_id and wecom_client is not None:
            articles = []
            for idx, item in enumerate(candidates[:8], start=1):
                air_date = item.get("first_air_date") or ""
                title = item.get("name") or item.get("original_name") or "未知剧名"
                tmdb_id = item.get("id")
                
                articles.append({
                    "title": f"{idx}. {title} ({air_date})",
                    "thumb_media_id": first_media_id,
                    "author": "Emby 缺集检测",
                    "content_source_url": "",
                    "content": f"TMDB ID: {tmdb_id}\\n\\n回复'资源 {idx}'查看 HDHive 资源",
                    "digest": f"TMDB:{tmdb_id} | 回复'资源 {idx}'查看详情",
                    "show_cover_pic": 1 if idx == 1 else 0,
                })
            
            try:
                wecom_client.send_mpnews_message(user_id, articles)
                return f"✅ 找到 {len(candidates)} 个候选，请查看图文消息\\n\\n回复'资源 序号'查看 HDHive 资源，例如：资源 1"
            except Exception as exc:
                logger.error(f"企业微信发送图文消息失败：{exc}")
        
        # 降级：发送文字消息
        lines = [f"找到 {len(candidates)} 个候选："]
        for idx, item in enumerate(candidates, start=1):
            air_date = item.get("first_air_date") or ""
            title = item.get("name") or item.get("original_name") or "未知剧名"
            tmdb_id = item.get("id")
            lines.append(f"{idx}. {title} {f'({air_date})' if air_date else ''} [TMDB:{tmdb_id}]")
        lines.append("")
        lines.append("回复'资源 序号'查看 HDHive 资源，例如：资源 1")
        return "\n".join(lines)

    def _send_poster_async(self, wecom_client: Any, user_id: str, poster_url: str) -> None:
        """在后台线程中上传海报并发送图片消息"""
        def _do():
            try:
                media_id = wecom_client.upload_media_image_url(poster_url)
                if media_id:
                    wecom_client.send_image_message(user_id, media_id)
            except Exception as exc:
                logger.warning(f"\u4f01\u4e1a\u5fae\u4fe1\u53d1\u9001\u6d77\u62a5\u56fe\u7247\u5931\u8d25: {exc}")

        threading.Thread(target=_do, daemon=True).start()

    def _search_resources(
        self,
        user_id: str,
        index: int,
        hdhive_client: Any,
        config_manager: Any,
        db: Any = None,
    ) -> str:
        if hdhive_client is None:
            return "HDHive \u672a\u914d\u7f6e\uff0c\u65e0\u6cd5\u67e5\u8be2\u8d44\u6e90\u3002"

        session = self._get_session(user_id, db=db)
        tmdb_results = session.get("tmdb_results", [])
        if not tmdb_results:
            return "\u6ca1\u6709\u53ef\u7528\u7684\u641c\u5267\u7ed3\u679c\u3002\u8bf7\u5148\u53d1\u9001\u201c\u641c\u7d22 \u5267\u540d\u201d\u3002"

        if index < 1 or index > len(tmdb_results):
            return f"\u5e8f\u53f7\u65e0\u6548\uff0c\u8bf7\u8f93\u5165 1 \u5230 {len(tmdb_results)}\u3002"

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
            logger.error(f"\u4f01\u4e1a\u5fae\u4fe1\u67e5\u8be2\u8d44\u6e90\u5931\u8d25: {exc}")
            return f"\u67e5\u8be2\u8d44\u6e90\u5931\u8d25\uff1a{exc}"

        if not resources:
            default_name = '\u672a\u77e5\u5267\u540d'
            return f"\u6ca1\u6709\u627e\u5230\u201c{target.get('name', default_name)}\u201d\u7684\u53ef\u7528\u8d44\u6e90\u3002"

        resource_results: List[Dict[str, Any]] = []
        for item in resources[:8]:
            normalized_pan_type = self._normalize_pan_type(
                item.get("pan_type"),
                item.get("title") or "",
            )
            resource_results.append(
                {
                    "slug": item.get("slug"),
                    "title": item.get("title") or "\u672a\u77e5\u8d44\u6e90",
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
            },
            db=db,
        )

        max_points = 0
        if config_manager is not None:
            max_points = config_manager.get_hdhive_config().get("settings", {}).get("max_points_per_unlock", 0)

        default_name = '\u672a\u77e5\u5267\u540d'
        lines = [f"{target.get('name', default_name)} \u7684\u8d44\u6e90\u5982\u4e0b\uff1a"]
        for idx, item in enumerate(resource_results, start=1):
            resolutions = "/".join(item.get("video_resolution") or []) or "-"
            sources = "/".join(item.get("source") or []) or "-"
            points = item.get("unlock_points", 0)
            extra = " \u5df2\u89e3\u9501" if item.get("is_unlocked") else ""
            if max_points and points > max_points:
                extra += " \u8d85\u8fc7\u79ef\u5206\u4e0a\u9650"

            pan_type = (item.get("pan_type") or "").strip()
            pan_name = self._pan_display_name(pan_type)
            pan_badge = f"[{pan_name}]" if pan_name else "[\u7f51\u76d8\u672a\u77e5]"

            unknown_pan = '\u672a\u77e5'
            lines.append(
                f"{idx}. {item['title']} {pan_badge}\n"
                f"\u79ef\u5206:{points} \u7f51\u76d8:{pan_name or unknown_pan} \u5206\u8fa8\u7387:{resolutions} \u6765\u6e90:{sources}{extra}"
            )

        lines.append("")
        lines.append("\u56de\u590d\u201c\u89e3\u9501 \u5e8f\u53f7\u201d\u83b7\u53d6\u94fe\u63a5\uff0c\u4f8b\u5982\uff1a\u89e3\u9501 1")
        return "\n".join(lines)

    def _unlock_resource(self, user_id: str, index: int, hdhive_client: Any, db: Any, config_manager: Any) -> str:
        if hdhive_client is None:
            return "HDHive \u672a\u914d\u7f6e\uff0c\u65e0\u6cd5\u89e3\u9501\u8d44\u6e90\u3002"

        session = self._get_session(user_id, db=db)
        resource_results = session.get("resource_results", [])
        if not resource_results:
            return "\u6ca1\u6709\u53ef\u7528\u7684\u8d44\u6e90\u5217\u8868\u3002\u8bf7\u5148\u53d1\u9001\u201c\u641c\u7d22 \u5267\u540d\u201d\uff0c\u518d\u53d1\u9001\u201c\u8d44\u6e90 \u5e8f\u53f7\u201d\u3002"

        if index < 1 or index > len(resource_results):
            return f"\u5e8f\u53f7\u65e0\u6548\uff0c\u8bf7\u8f93\u5165 1 \u5230 {len(resource_results)}\u3002"

        target = resource_results[index - 1]
        points = int(target.get("unlock_points", 0) or 0)

        max_points = 0
        if config_manager is not None:
            max_points = config_manager.get_hdhive_config().get("settings", {}).get("max_points_per_unlock", 0)
        if max_points and points > max_points:
            return f"\u8be5\u8d44\u6e90\u9700\u8981 {points} \u79ef\u5206\uff0c\u8d85\u8fc7\u5f53\u524d\u9650\u5236 {max_points}\uff0c\u5df2\u963b\u6b62\u89e3\u9501\u3002"

        try:
            result = hdhive_client.unlock_resource(target["slug"])
        except Exception as exc:
            logger.error(f"\u4f01\u4e1a\u5fae\u4fe1\u89e3\u9501\u5931\u8d25: {exc}")
            return f"\u89e3\u9501\u5931\u8d25\uff1a{exc}"

        link = result.get("full_url") or result.get("url") or ""
        access_code = result.get("access_code", "")
        if link and access_code and "\u63d0\u53d6\u7801" not in link and "pwd=" not in link:
            link = f"{link} \u63d0\u53d6\u7801: {access_code}"

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
                logger.warning(f"\u4fdd\u5b58\u4f01\u4e1a\u5fae\u4fe1\u89e3\u9501\u8bb0\u5f55\u5931\u8d25: {exc}")

        status_text = "\u5df2\u62e5\u6709\u8be5\u8d44\u6e90" if result.get("already_owned") else "\u89e3\u9501\u6210\u529f"
        pan_type = (target.get("pan_type") or "").strip()
        unknown_text = '\u672a\u77e5'
        lines = [
            status_text,
            f"\u5267\u96c6: {target.get('series_name') or unknown_text}",
            f"\u8d44\u6e90: {target.get('title') or unknown_text}",
            f"\u7f51\u76d8: {self._pan_display_name(pan_type) or unknown_text}",
        ]
        if link:
            lines.append(f"\u94fe\u63a5: {link}")
        if access_code and "\u63d0\u53d6\u7801" not in link:
            lines.append(f"\u63d0\u53d6\u7801: {access_code}")

        spent = result.get("points_spent")
        if spent is None:
            spent = points
        lines.append(f"\u79ef\u5206\u6d88\u8017: {spent}")

        # 尝试自动转存到 Symedia
        raw_url = result.get("full_url") or result.get("url") or ""
        if raw_url and config_manager is not None:
            transfer_result = self._transfer_to_symedia(raw_url, access_code, config_manager)
            if transfer_result:
                lines.append(transfer_result)

        return "\n".join(lines)

    def _transfer_to_symedia(self, url: str, access_code: str, config_manager: Any) -> str:
        """调用 Symedia 转存接口，返回结果提示文字。"""
        try:
            cfg = config_manager.get_symedia_config()
        except Exception:
            return ""
        host = (cfg.get("host") or "").strip()
        if not host or not cfg.get("enabled", True):
            return ""
        token = (cfg.get("token") or "symedia").strip() or "symedia"
        parent_id = str(cfg.get("parent_id") or "0").strip() or "0"

        full_url = url
        if access_code and "password=" not in full_url:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}password={access_code}"

        import httpx
        api_url = f"{host.rstrip('/')}/api/v1/plugin/cloud_helper/add_share_urls_115"
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    api_url,
                    params={"token": token},
                    json={"urls": [full_url], "parent_id": parent_id},
                    headers={"Content-Type": "application/json"},
                )
            if resp.status_code == 200:
                logger.info(f"\u4f01\u4e1a\u5fae\u4fe1\u89e3\u9501\u540e Symedia \u8f6c\u5b58\u6210\u529f: {url}")
                return "\u2705 \u5df2\u81ea\u52a8\u8f6c\u5b58\u5230 Symedia"
            else:
                logger.warning(f"Symedia \u8f6c\u5b58\u5931\u8d25: status={resp.status_code}")
                return f"\u26a0\ufe0f \u8f6c\u5b58\u5931\u8d25(HTTP {resp.status_code})"
        except Exception as exc:
            logger.warning(f"Symedia \u8f6c\u5b58\u5f02\u5e38: {exc}")
            return f"\u26a0\ufe0f \u8f6c\u5b58\u5f02\u5e38: {exc}"

    def _latest_history(self, db: Any) -> str:
        if db is None:
            return "\u6570\u636e\u5e93\u672a\u521d\u59cb\u5316\uff0c\u65e0\u6cd5\u67e5\u770b\u89e3\u9501\u5386\u53f2\u3002"

        try:
            records = db.get_hdhive_unlocks(limit=5)
        except Exception as exc:
            logger.error(f"\u83b7\u53d6\u4f01\u4e1a\u5fae\u4fe1\u89e3\u9501\u5386\u53f2\u5931\u8d25: {exc}")
            return f"\u8bfb\u53d6\u5386\u53f2\u5931\u8d25\uff1a{exc}"

        if not records:
            return "\u6682\u65e0\u89e3\u9501\u5386\u53f2\u3002"

        lines = ["\u6700\u8fd1 5 \u6761\u89e3\u9501\u8bb0\u5f55\uff1a"]
        for idx, item in enumerate(records, start=1):
            title = item.get("title") or item.get("series_name") or item.get("slug") or "\u672a\u77e5"
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
                logger.warning(f"\u4fdd\u5b58\u4f01\u4e1a\u5fae\u4fe1\u4f1a\u8bdd\u5931\u8d25: {exc}")

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
                    logger.warning(f"\u5237\u65b0\u4f01\u4e1a\u5fae\u4fe1\u4f1a\u8bdd\u5931\u8d25: {exc}")
            return dict(payload)

        if db is None:
            return {}

        try:
            payload = db.get_wecom_session(user_id, self.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.warning(f"\u8bfb\u53d6\u4f01\u4e1a\u5fae\u4fe1\u4f1a\u8bdd\u5931\u8d25: {exc}")
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
                logger.warning(f"\u5220\u9664\u4f01\u4e1a\u5fae\u4fe1\u4f1a\u8bdd\u5931\u8d25: {exc}")

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
            "\u53ef\u7528\u547d\u4ee4\uff1a\n"
            "1. \u641c\u7d22 \u5267\u540d\n"
            "2. \u8d44\u6e90 \u5e8f\u53f7\n"
            "3. \u89e3\u9501 \u5e8f\u53f7\n"
            "4. \u5386\u53f2\n"
            "5. \u91cd\u7f6e"
        )

    @staticmethod
    def _pan_display_name(pan_type: str) -> str:
        normalized = (pan_type or "").strip().lower()
        if normalized in {"115"}:
            return "115"
        if normalized in {"ali", "aliyun", "alipan"}:
            return "\u963f\u91cc\u4e91\u76d8"
        if normalized in {"quark"}:
            return "\u5938\u514b"
        if normalized in {"baidu", "bd"}:
            return "\u767e\u5ea6\u7f51\u76d8"
        if normalized in {"xunlei", "thunder"}:
            return "\u8fc5\u96f7"
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
        if "\u963f\u91cc" in title or "aliyun" in text or "alipan" in text:
            return "ali"
        if "\u5938\u514b" in title or "quark" in text:
            return "quark"
        if "\u767e\u5ea6" in title or "baidu" in text:
            return "baidu"
        if "\u8fc5\u96f7" in title or "xunlei" in text or "thunder" in text:
            return "xunlei"
        return raw
