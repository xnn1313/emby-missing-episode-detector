"""
Emby 缺集检测系统 - 主程序入口
参考 MoviePilot 设计，基于 FastAPI
"""

import os
import sys
import hashlib
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Any, Dict
from loguru import logger
import uvicorn

from app.emby_client import EmbyClient, EmbyClientError
from app.detector import MissingEpisodeDetector
from app.tmdb_client import TMDBClient, TMDBMatcher
from app.notifier import setup_notifiers_from_env, NotificationManager
from app.telegram_notifier import setup_telegram_from_env, TelegramNotifier
from app.scheduler import DetectionScheduler
from app.database import get_database, Database
from app.export import ReportExporter
from app.config_manager import get_config_manager, ConfigManager
from app.auth import AUTH_AVAILABLE, create_access_token, get_user_database, verify_access_token
from app.wecom_command_service import WeComCommandService

MASKED_SECRET = "***"
auth_scheme = HTTPBearer(auto_error=False)

def setup_logging():
    """配置日志（延迟初始化，避免导入时副作用）"""
    logger.remove()
    logger.add(
        project_root / "logs" / "emby-detector.log",
        level="INFO",
        rotation="100 MB",
        retention="7 days",
        mode='a'
    )
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

# 创建 FastAPI 应用
app = FastAPI(
    title="Emby 缺集检测系统",
    description="基于 MoviePilot 设计理念的 Emby 媒体库缺集检测工具",
    version="0.1.0"
)


@app.on_event("startup")
async def startup_event():
    """应用启动时自动加载配置并初始化客户端"""
    global emby_client, detector, db, config_manager, moviepilot_client, hdhive_client, last_result
    
    try:
        # 初始化日志
        setup_logging()
        logger.info("正在启动服务...")

        config_manager = get_config_manager()
        config = config_manager.get_all_config()
        _apply_runtime_config(config)
        
        logger.info("服务启动完成")
    except Exception as e:
        logger.error(f"启动失败：{e}")


# 全局变量（通过依赖注入管理，避免导入时初始化）
emby_client: Optional[EmbyClient] = None
tmdb_client: Optional[TMDBClient] = None
tmdb_matcher: Optional[TMDBMatcher] = None
detector: Optional[MissingEpisodeDetector] = None
notifier_manager: Optional[NotificationManager] = None
telegram_notifier: Optional[TelegramNotifier] = None
db: Optional[Database] = None
exporter: Optional[ReportExporter] = None
detection_scheduler: Optional[DetectionScheduler] = None
config_manager: Optional[ConfigManager] = None
moviepilot_client: Optional[Any] = None
hdhive_client: Optional[Any] = None
wecom_client: Optional[Any] = None
wecom_command_service = WeComCommandService()
last_result = None


# ============ 数据模型 ============

class EmbyConfig(BaseModel):
    """Emby 配置"""
    host: str = ""
    api_key: str = ""


class LibraryConfig(BaseModel):
    """媒体库配置"""
    enabled: bool = False
    selected_ids: List[str] = Field(default_factory=list)


class MoviePilotConfig(BaseModel):
    """MoviePilot 配置"""
    host: str = ""
    username: str = "admin"
    password: str = ""
    enabled: bool = False
    auto_download: bool = True
    download_path: str = ""


class TMDBConfig(BaseModel):
    """TMDB 配置"""
    enabled: bool = False
    api_key: str = ""


class DetectionConfig(BaseModel):
    """检测配置"""
    interval_minutes: int = 60
    auto_start: bool = True


class WeComConfigModel(BaseModel):
    """企业微信配置"""
    enabled: bool = False
    corp_id: str = ""
    agent_id: int = 0
    corp_secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"


class FullConfig(BaseModel):
    """完整配置"""
    emby: Optional[EmbyConfig] = None
    libraries: Optional[LibraryConfig] = None
    tmdb: Optional[TMDBConfig] = None
    detection: Optional[DetectionConfig] = None
    moviepilot: Optional[MoviePilotConfig] = None
    wecom: Optional[WeComConfigModel] = None

    # 兼容旧版扁平字段
    host: Optional[str] = None
    api_key: Optional[str] = None
    tmdb_api_key: Optional[str] = None
    detection_interval: Optional[int] = None

    @model_validator(mode="after")
    def apply_legacy_fields(self):
        if self.emby is None:
            self.emby = EmbyConfig(
                host=self.host or "",
                api_key=self.api_key or ""
            )
        if self.libraries is None:
            self.libraries = LibraryConfig()
        if self.tmdb is None:
            self.tmdb = TMDBConfig(
                enabled=bool(self.tmdb_api_key),
                api_key=self.tmdb_api_key or ""
            )
        if self.detection is None:
            self.detection = DetectionConfig(
                interval_minutes=self.detection_interval or 60,
                auto_start=True
            )
        if self.moviepilot is None:
            self.moviepilot = MoviePilotConfig()
        return self


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class DetectionStatus(BaseModel):
    """检测状态（扩展信息）"""
    status: str
    message: str = ""
    total_series: int = 0
    series_with_missing: int = 0
    total_missing: int = 0
    last_detection: Optional[str] = None


class MissingEpisode(BaseModel):
    """缺失的集"""
    series_name: str
    season: int
    episodes: List[int]


def _mask_secret(value: str) -> str:
    return MASKED_SECRET if value else ""


def _resolve_secret(new_value: str, existing_value: str) -> str:
    if new_value == MASKED_SECRET:
        return existing_value or ""
    return new_value or ""


def _build_public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    public_config = {
        "emby": dict(config.get("emby", {})),
        "libraries": dict(config.get("libraries", {})),
        "tmdb": dict(config.get("tmdb", {})),
        "detection": dict(config.get("detection", {})),
        "moviepilot": dict(config.get("moviepilot", {})),
        "wecom": dict(config.get("wecom", {}))
    }

    public_config["emby"]["api_key"] = _mask_secret(public_config["emby"].get("api_key", ""))
    public_config["tmdb"]["api_key"] = _mask_secret(public_config["tmdb"].get("api_key", ""))
    public_config["moviepilot"]["password"] = _mask_secret(public_config["moviepilot"].get("password", ""))
    public_config["wecom"]["corp_secret"] = _mask_secret(public_config["wecom"].get("corp_secret", ""))
    public_config["wecom"]["token"] = _mask_secret(public_config["wecom"].get("token", ""))
    public_config["wecom"]["encoding_aes_key"] = _mask_secret(public_config["wecom"].get("encoding_aes_key", ""))

    return public_config


def _build_persisted_config(config: FullConfig, existing: Dict[str, Any]) -> Dict[str, Any]:
    emby_existing = existing.get("emby", {})
    tmdb_existing = existing.get("tmdb", {})
    detection_existing = existing.get("detection", {})
    moviepilot_existing = existing.get("moviepilot", {})
    libraries_existing = existing.get("libraries", {})
    hdhive_existing = existing.get("hdhive", {})
    wecom_existing = existing.get("wecom", {})

    emby_config = {
        "host": (config.emby.host or "").strip(),
        "api_key": _resolve_secret((config.emby.api_key or "").strip(), emby_existing.get("api_key", ""))
    }

    tmdb_api_key = _resolve_secret((config.tmdb.api_key or "").strip(), tmdb_existing.get("api_key", ""))
    tmdb_config = {
        "enabled": config.tmdb.enabled and bool(tmdb_api_key),
        "api_key": tmdb_api_key
    }

    detection_config = {
        "interval_minutes": max(1, config.detection.interval_minutes),
        "auto_start": bool(config.detection.auto_start)
    }

    moviepilot_password = _resolve_secret(
        (config.moviepilot.password or "").strip(),
        moviepilot_existing.get("password", "")
    )
    moviepilot_config = {
        "host": (config.moviepilot.host or "").strip(),
        "username": (config.moviepilot.username or "admin").strip() or "admin",
        "password": moviepilot_password,
        "enabled": bool(config.moviepilot.enabled),
        "auto_download": bool(config.moviepilot.auto_download),
        "download_path": (config.moviepilot.download_path or "").strip()
    }

    if config.wecom is not None:
        wecom_config = {
            "enabled": bool(config.wecom.enabled),
            "corp_id": (config.wecom.corp_id or "").strip(),
            "agent_id": int(config.wecom.agent_id or 0),
            "corp_secret": _resolve_secret(
                (config.wecom.corp_secret or "").strip(),
                wecom_existing.get("corp_secret", "")
            ),
            "token": _resolve_secret(
                (config.wecom.token or "").strip(),
                wecom_existing.get("token", "")
            ),
            "encoding_aes_key": _resolve_secret(
                (config.wecom.encoding_aes_key or "").strip(),
                wecom_existing.get("encoding_aes_key", "")
            ),
            "base_url": (config.wecom.base_url or "https://qyapi.weixin.qq.com/cgi-bin").strip()
        }
    else:
        wecom_config = dict(wecom_existing)

    return {
        "emby": emby_config,
        "libraries": {
            "enabled": bool(config.libraries.enabled),
            "selected_ids": list(config.libraries.selected_ids or [])
        } if config.libraries else dict(libraries_existing),
        "tmdb": tmdb_config,
        "detection": detection_config,
        "moviepilot": moviepilot_config,
        "hdhive": dict(hdhive_existing),
        "wecom": wecom_config
    }


def _cleanup_runtime_components():
    global emby_client, tmdb_client, tmdb_matcher, detector, notifier_manager, db
    global exporter, detection_scheduler, moviepilot_client, hdhive_client, wecom_client

    if detection_scheduler is not None:
        try:
            detection_scheduler.shutdown()
        except Exception as exc:
            logger.warning(f"关闭旧调度器失败：{exc}")
        detection_scheduler = None

    for client_name in ("emby_client", "moviepilot_client", "hdhive_client", "tmdb_client", "wecom_client"):
        client = globals().get(client_name)
        if client is not None and hasattr(client, "close"):
            try:
                client.close()
            except Exception as exc:
                logger.warning(f"关闭 {client_name} 失败：{exc}")
        globals()[client_name] = None

    tmdb_matcher = None
    detector = None
    notifier_manager = None
    db = None
    exporter = None


def _build_proxy_url(proxy_config: Optional[Dict[str, Any]]) -> str:
    if not proxy_config or not proxy_config.get("enabled") or not proxy_config.get("host"):
        return ""

    host = str(proxy_config.get("host", "")).strip()
    port = int(proxy_config.get("port", 0) or 0)
    username = str(proxy_config.get("username", "")).strip()
    password = str(proxy_config.get("password", "")).strip()

    if not host or not port:
        return ""

    if username and password:
        return f"http://{username}:{password}@{host}:{port}"
    return f"http://{host}:{port}"


def _apply_runtime_config(config: Dict[str, Any]):
    global emby_client, tmdb_client, tmdb_matcher, detector, notifier_manager, db
    global exporter, detection_scheduler, moviepilot_client, hdhive_client, wecom_client

    _cleanup_runtime_components()

    db = get_database()
    exporter = ReportExporter()

    emby_config = config.get("emby", {})
    tmdb_config = config.get("tmdb", {})
    lib_config = config.get("libraries", {})
    detection_config = config.get("detection", {})
    mp_config = config.get("moviepilot", {})
    hd_config = config.get("hdhive", {})
    wecom_config = config.get("wecom", {})
    tmdb_proxy_url = _build_proxy_url(hd_config.get("proxy"))

    if emby_config.get("host") and emby_config.get("api_key"):
        emby_client = EmbyClient(emby_config["host"], emby_config["api_key"])
        logger.info(f"Emby 客户端已初始化：{emby_config['host']}")
    else:
        logger.warning("⚠️ Emby 配置未找到，请在配置页面设置")

    if tmdb_config.get("enabled") and tmdb_config.get("api_key"):
        tmdb_client = TMDBClient(tmdb_config["api_key"], proxy_url=tmdb_proxy_url)
        tmdb_matcher = TMDBMatcher(tmdb_client)
        logger.info(f"TMDB 客户端已初始化（代理：{'启用' if tmdb_proxy_url else '禁用'}）")

    library_ids = lib_config.get("selected_ids", []) if lib_config.get("enabled") else None
    detector = MissingEpisodeDetector(tmdb_matcher=tmdb_matcher, library_ids=library_ids)
    notifier_manager = setup_notifiers_from_env()

    if mp_config.get("enabled") and mp_config.get("host"):
        from app.moviepilot_client import MoviePilotClient
        moviepilot_client = MoviePilotClient(
            host=mp_config["host"],
            username=mp_config.get("username", "admin"),
            password=mp_config.get("password", "")
        )
        detector.moviepilot_client = moviepilot_client
        logger.info(f"MoviePilot 客户端已初始化：{mp_config['host']}")

    if hd_config.get("enabled") and hd_config.get("api_key"):
        from app.hdhive_client import create_client_from_config
        hdhive_client = create_client_from_config(hd_config)
        logger.info("HDHive 客户端已初始化")

    if wecom_config.get("enabled"):
        from app.wecom_client import create_client_from_config as create_wecom_client
        try:
            wecom_client = create_wecom_client(wecom_config)
            logger.info("企业微信客户端已初始化")
        except Exception as exc:
            wecom_client = None
            logger.error(f"企业微信客户端初始化失败: {exc}")

    interval = detection_config.get("interval_minutes", 60)
    auto_start = detection_config.get("auto_start", True)
    if auto_start and emby_client is not None:
        detection_scheduler = DetectionScheduler(emby_client, detector, notifier_manager)
        detection_scheduler.start_auto_detection(interval_minutes=interval)
    elif auto_start:
        logger.warning("⚠️ 跳过自动检测启动：Emby 客户端不可用")

    if emby_client is not None:
        if emby_client.test_connection():
            logger.info("✅ Emby 连接测试成功")
        else:
            logger.warning("⚠️ Emby 连接测试失败，请检查配置")


def _build_wecom_message_key(message: Dict[str, Any]) -> str:
    """构造企业微信消息幂等键，优先使用消息 ID。"""
    msg_id = str(message.get("MsgId") or message.get("MsgId64") or "").strip()
    if msg_id:
        return f"msgid:{msg_id}"

    raw = "|".join([
        str(message.get("FromUserName") or ""),
        str(message.get("ToUserName") or ""),
        str(message.get("CreateTime") or ""),
        str(message.get("MsgType") or ""),
        str(message.get("Event") or ""),
        str(message.get("EventKey") or ""),
        str(message.get("Content") or ""),
    ])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"fallback:{digest}"


def _build_wecom_reply_text(
    message: Dict[str, Any],
    current_tmdb_client: Any,
    current_hdhive_client: Any,
    current_db: Any,
    current_config_manager: Any,
) -> str:
    msg_type = (message.get("MsgType") or "").lower()
    from_user = message.get("FromUserName", "")

    if msg_type == "text":
        return wecom_command_service.handle_text_message(
            user_id=from_user,
            content=message.get("Content", ""),
            tmdb_client=current_tmdb_client,
            hdhive_client=current_hdhive_client,
            db=current_db,
            config_manager=current_config_manager,
        )

    if msg_type == "event":
        return (
            "已接入剧集搜索。\n"
            "发送“搜索 剧名”开始，例如：搜索 黑镜"
        )

    return "当前只支持文本命令。\n发送“帮助”查看用法。"


def _process_wecom_message_async(
    dedupe_key: str,
    message: Dict[str, Any],
    current_wecom_client: Any,
    current_tmdb_client: Any,
    current_hdhive_client: Any,
    current_db: Any,
    current_config_manager: Any,
):
    """后台处理企业微信消息并主动发送结果，避免回调超时。"""
    from_user = message.get("FromUserName", "")
    msg_type = (message.get("MsgType") or "").lower()

    try:
        reply_text = _build_wecom_reply_text(
            message=message,
            current_tmdb_client=current_tmdb_client,
            current_hdhive_client=current_hdhive_client,
            current_db=current_db,
            current_config_manager=current_config_manager,
        )

        current_wecom_client.send_text_message(from_user, reply_text)
        if current_db is not None:
            current_db.complete_wecom_message(dedupe_key, reply_text, "async")

        logger.info(
            "企业微信异步回复发送成功: msg_type={}, from_user={}, reply_length={}",
            msg_type or "unknown",
            from_user or "unknown",
            len(reply_text),
        )
    except Exception as exc:
        if current_db is not None:
            try:
                current_db.fail_wecom_message(dedupe_key, str(exc))
            except Exception as db_exc:
                logger.warning(f"记录企业微信消息失败状态时出错: {db_exc}")
        logger.error(f"企业微信异步处理失败: {exc}")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(auth_scheme)) -> Dict[str, Any]:
    if not AUTH_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块不可用"
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = verify_access_token(credentials.credentials)
    username = payload.get("sub") if payload else None
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = get_user_database().get_user(username)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不可用",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


# ============ API 路由 ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页 - 重定向到海报墙"""
    from fastapi.responses import HTMLResponse
    with open(static_path / "index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """管理员登录"""
    if not AUTH_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块不可用"
        )

    user_db = get_user_database()
    user = user_db.authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    user_db.update_last_login(request.username)
    access_token = create_access_token({
        "sub": user["username"],
        "role": user.get("role", "user")
    })

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "role": user.get("role", "user")
        }
    }


@app.get("/api/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取当前登录用户"""
    return {
        "status": "success",
        "user": {
            "username": current_user["username"],
            "role": current_user.get("role", "user")
        }
    }

@app.post("/api/auth/password")
async def change_password(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    new_password = (payload.get("new_password") or "").strip()
    if not new_password:
        raise HTTPException(status_code=400, detail="新密码不能为空")
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改密码")
    user_db = get_user_database()
    ok = user_db.set_password(current_user["username"], new_password)
    if not ok:
        raise HTTPException(status_code=500, detail="密码更新失败")
    return {"status": "success"}

@app.post("/api/auth/account")
async def change_account(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改账号")
    new_username = (payload.get("new_username") or "").strip()
    new_password = (payload.get("new_password") or "").strip()
    user_db = get_user_database()
    changed = False
    if new_username:
        if not user_db.set_username(current_user["username"], new_username):
            raise HTTPException(status_code=400, detail="用户名更新失败或已存在")
        changed = True
    if new_password:
        if not user_db.set_password(new_username or current_user["username"], new_password):
            raise HTTPException(status_code=500, detail="密码更新失败")
        changed = True
    return {"status": "success", "require_relogin": changed}


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if emby_client is None:
        return {"status": "not_configured", "message": "Emby 未配置"}
    
    if emby_client.test_connection():
        return {"status": "connected", "message": "Emby 连接正常"}
    else:
        return {"status": "disconnected", "message": "Emby 连接失败"}


@app.get("/api/libraries")
async def get_libraries(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取 Emby 媒体库列表"""
    if emby_client is None:
        raise HTTPException(status_code=400, detail="Emby 未配置")
    
    try:
        libraries = emby_client.get_media_libraries()
        
        # 过滤出剧集库
        tv_libraries = []
        for lib in libraries:
            # 检查是否包含剧集内容
            collection_type = lib.get('CollectionType', '')
            name = lib.get('Name', '')
            lib_id = lib.get('ItemId', lib.get('Name', ''))
            
            # 电视剧库通常 collection_type 为 tvshows 或包含 TV 字样
            if collection_type == 'tvshows' or 'TV' in name or '剧集' in name or '电视剧' in name:
                tv_libraries.append({
                    'id': lib_id,
                    'name': name,
                    'type': collection_type or 'unknown',
                    'locations': lib.get('Locations', [])
                })
        
        # 如果没有找到明确的 TV 库，返回所有视频库
        if not tv_libraries:
            for lib in libraries:
                collection_type = lib.get('CollectionType', '')
                if collection_type in ['movies', 'tvshows', 'homevideos', '']:
                    tv_libraries.append({
                        'id': lib.get('ItemId', lib.get('Name', '')),
                        'name': lib.get('Name', ''),
                        'type': collection_type or 'unknown',
                        'locations': lib.get('Locations', [])
                    })
        
        return {
            "status": "success",
            "libraries": tv_libraries,
            "total": len(tv_libraries)
        }
    except Exception as e:
        logger.error(f"获取媒体库失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取当前配置"""
    global config_manager
    
    if config_manager is None:
        config_manager = get_config_manager()
    
    return {
        "status": "success",
        "config": _build_public_config(config_manager.get_all_config())
    }


@app.post("/api/config")
async def set_config(config: FullConfig, current_user: Dict[str, Any] = Depends(get_current_user)):
    """设置完整配置（支持媒体库配置）"""
    global config_manager, last_result
    
    try:
        config_manager = get_config_manager()
        existing_config = config_manager.get_all_config()
        new_config = _build_persisted_config(config, existing_config)

        if not config_manager.update_config(new_config):
            raise HTTPException(status_code=500, detail="配置保存失败")

        _apply_runtime_config(new_config)
        last_result = None

        library_ids = new_config.get("libraries", {}).get("selected_ids", []) if new_config.get("libraries", {}).get("enabled") else []
        interval = new_config.get("detection", {}).get("interval_minutes", 60)
        auto_start = new_config.get("detection", {}).get("auto_start", True)

        if not new_config.get("emby", {}).get("host") or not new_config.get("emby", {}).get("api_key"):
            return {
                "status": "success",
                "message": "配置已保存，但 Emby 配置仍不完整",
                "config": _build_public_config(new_config)
            }

        if emby_client and emby_client.test_connection():
            return {
                "status": "success",
                "message": "配置成功，Emby 连接正常",
                "scheduler": f"{'定时检测已启动' if auto_start else '定时检测未启动'} (每{interval}分钟)",
                "library_filter": f"{'启用' if library_ids else '禁用'} ({len(library_ids)}个库)",
                "config": _build_public_config(new_config)
            }

        return {
            "status": "error",
            "message": "配置已保存，但 Emby 连接失败，请检查配置",
            "config": _build_public_config(new_config)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置失败：{e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/detect")
async def run_detection(current_user: Dict[str, Any] = Depends(get_current_user)):
    """运行缺集检测（异步模式，立即返回）"""
    global last_result
    
    if emby_client is None:
        raise HTTPException(status_code=400, detail="Emby 未配置")
    
    if detector is None:
        raise HTTPException(status_code=400, detail="检测器未初始化")

    if not emby_client.test_connection():
        raise HTTPException(status_code=502, detail=f"无法连接到 Emby 服务器：{emby_client.host}")
    
    try:
        logger.info("=" * 50)
        logger.info("开始手动检测...")
        logger.info(f"Emby 地址：{emby_client.host}")
        logger.info(f"TMDB 启用：{detector.use_tmdb}")
        logger.info(f"媒体库过滤：{detector.use_library_filter}")
        
        # 在后台线程中运行检测，避免阻塞
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        
        def detect_task():
            try:
                logger.info("检测任务开始执行...")
                result = detector.detect(emby_client)
                logger.info(f"检测任务执行完成：{result.total_series} 个剧集")
                return result
            except Exception as e:
                logger.error(f"检测任务内部异常：{e}", exc_info=True)
                raise
        
        # 使用 with 语句确保 ThreadPoolExecutor 正确关闭
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(detect_task)
            
            try:
                # 设置超时（15 分钟，给大库足够时间）
                logger.info("等待检测结果（超时时间：15 分钟）...")
                last_result = future.result(timeout=900)
            except TimeoutError:
                logger.error("检测超时（>15 分钟）")
                future.cancel()
                raise HTTPException(status_code=504, detail="检测超时，请减少媒体库数量后重试")
            except Exception as e:
                logger.error(f"检测任务执行失败：{e}", exc_info=True)
                raise
        
        # 保存到数据库
        if db:
            logger.info("保存检测结果到数据库...")
            db.save_detection_result(last_result)
        
        # 发送通知
        if notifier_manager and last_result.series_with_missing > 0:
            logger.info("发送缺集通知...")
            notifier_manager.send_missing_report(last_result)
        
        logger.info("=" * 50)
        logger.info(f"检测完成：{last_result.series_with_missing}/{last_result.total_series} 有缺集")
        logger.info(f"缺失总集数：{last_result.total_missing_episodes}")
        logger.info(f"耗时：{last_result.duration_seconds:.2f}秒")
        
        return {
            "status": "success",
            "summary": detector.get_summary(last_result),
            "stats": {
                "total_series": last_result.total_series,
                "series_with_missing": last_result.series_with_missing,
                "total_missing_episodes": last_result.total_missing_episodes
            },
            "saved_to_db": db is not None,
            "notified": notifier_manager is not None and last_result.series_with_missing > 0
        }
    except EmbyClientError as e:
        logger.error(f"Emby 数据获取失败：{e}")
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检测失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results")
async def get_results(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取检测结果"""
    if last_result is None:
        return {"status": "no_data", "message": "暂无检测结果"}
    
    # 转换为 JSON 格式
    results = []
    for series in last_result.series:
        if series.missing_episodes_count > 0:
            for season in series.seasons:
                if season.missing_episodes:
                    results.append({
                        "series_name": series.series_name,
                        "season": season.season_number,
                        "missing_episodes": season.missing_episodes
                    })
    
    return {
        "status": "success",
        "results": results,
        "stats": {
            "total_series": last_result.total_series,
            "series_with_missing": last_result.series_with_missing,
            "total_missing_episodes": last_result.total_missing_episodes
        }
    }


@app.get("/api/tmdb/search")
async def search_tmdb_by_name(name: str):
    """通过剧集名称搜索 TMDB ID"""
    import httpx
    
    # 获取 TMDB API Key（可选）
    tmdb_config = config_manager.get_tmdb_config() if config_manager else {}
    all_config = config_manager.get_all_config() if config_manager else {}
    tmdb_proxy_url = _build_proxy_url((all_config.get("hdhive") or {}).get("proxy"))
    tmdb_api_key = tmdb_config.get('api_key', '')
    
    logger.info(
        f"TMDB 搜索请求：name={name}, api_key={'已配置' if tmdb_api_key else '未配置'}, "
        f"proxy={'启用' if tmdb_proxy_url else '禁用'}"
    )
    
    if not tmdb_api_key:
        # 使用公共 API Key 或返回错误
        return {"status": "error", "message": "请先在配置中设置 TMDB API Key"}
    
    try:
        # 调用 TMDB 搜索 API
        search_url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={name}&language=zh-CN"
        
        async_client_kwargs: Dict[str, Any] = {"timeout": 10}
        if tmdb_proxy_url:
            async_client_kwargs["proxies"] = {
                "http://": tmdb_proxy_url,
                "https://": tmdb_proxy_url,
            }

        async with httpx.AsyncClient(**async_client_kwargs) as client:
            resp = await client.get(search_url)
            
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            if results:
                tmdb_id = str(results[0].get('id'))
                title = results[0].get('name', name)
                year = results[0].get('first_air_date', '')[:4]
                logger.info(f"TMDB 搜索成功: {name} -> {tmdb_id} ({title})")
                return {
                    "status": "success",
                    "tmdb_id": tmdb_id,
                    "title": title,
                    "year": year
                }
            else:
                return {"status": "not_found", "message": f"未找到: {name}"}
        else:
            return {"status": "error", "message": "TMDB API 请求失败"}
            
    except Exception as e:
        logger.error(f"TMDB 搜索失败: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/tmdb/candidates")
async def search_tmdb_candidates(
    name: str,
    year: int = None,
    limit: int = 5,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    global config_manager, tmdb_client

    if config_manager is None:
        config_manager = get_config_manager()

    tmdb_config = config_manager.get_tmdb_config() if config_manager else {}
    all_config = config_manager.get_all_config() if config_manager else {}
    tmdb_proxy_url = _build_proxy_url((all_config.get("hdhive") or {}).get("proxy"))
    tmdb_api_key = (tmdb_config.get("api_key") or "").strip()

    if not tmdb_api_key:
        raise HTTPException(status_code=400, detail="请先在配置中设置 TMDB API Key")

    safe_limit = max(1, min(int(limit or 5), 10))

    temp_client: Optional[TMDBClient] = None
    client = tmdb_client
    if client is None:
        temp_client = TMDBClient(api_key=tmdb_api_key, language="zh-CN", proxy_url=tmdb_proxy_url)
        client = temp_client

    try:
        candidates = client.search_tv_series_candidates(
            title=name,
            year=year,
            limit=safe_limit,
        )
    finally:
        if temp_client is not None:
            try:
                temp_client.client.close()
            except Exception:
                pass

    normalized = []
    for item in candidates or []:
        first_air_date = item.get("first_air_date") or ""
        normalized.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("original_name") or "",
                "original_name": item.get("original_name") or "",
                "first_air_date": first_air_date,
                "year": first_air_date[:4] if first_air_date else "",
                "overview": item.get("overview") or "",
                "poster_path": item.get("poster_path") or "",
            }
        )

    return {"status": "success", "count": len(normalized), "candidates": normalized}


@app.get("/api/tmdb/{series_id}")
async def get_tmdb_id(series_id: str):
    """获取剧集的 TMDB ID"""
    global emby_client
    
    if emby_client is None:
        raise HTTPException(status_code=400, detail="Emby 未配置")
    
    try:
        # 先尝试从 Emby 获取
        tmdb_id = emby_client.get_tmdb_id(series_id)
        if tmdb_id:
            return {"status": "success", "series_id": series_id, "tmdb_id": tmdb_id}
        
        # 如果没有，尝试获取剧集名称并通过名称搜索
        item = emby_client.get_item(series_id)
        if item:
            name = item.get('Name', '')
            year = item.get('ProductionYear', '')
            
            # 尝试通过 TMDB API 搜索
            tmdb_config = config_manager.get_tmdb_config() if config_manager else {}
            all_config = config_manager.get_all_config() if config_manager else {}
            tmdb_proxy_url = _build_proxy_url((all_config.get("hdhive") or {}).get("proxy"))
            if tmdb_config.get('api_key'):
                import httpx
                tmdb_api_key = tmdb_config['api_key']
                search_url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={name}"
                if year:
                    search_url += f"&first_air_date_year={year}"

                request_kwargs: Dict[str, Any] = {"timeout": 10}
                if tmdb_proxy_url:
                    request_kwargs["proxies"] = {
                        "http://": tmdb_proxy_url,
                        "https://": tmdb_proxy_url,
                    }

                resp = httpx.get(search_url, **request_kwargs)
                if resp.status_code == 200:
                    results = resp.json().get('results', [])
                    if results:
                        tmdb_id = str(results[0].get('id'))
                        logger.info(f"通过 TMDB API 搜索到：{name} -> {tmdb_id}")
                        return {"status": "success", "series_id": series_id, "tmdb_id": tmdb_id, "source": "search"}
            
            return {
                "status": "not_found", 
                "series_id": series_id, 
                "message": "未找到 TMDB ID",
                "hint": "请检查剧集刮削信息或配置 TMDB API Key"
            }
        else:
            return {"status": "not_found", "series_id": series_id, "message": "未找到剧集信息"}
            
    except Exception as e:
        logger.error(f"获取 TMDB ID 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cards")
async def get_cards(page: int = 1, page_size: int = 20, current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取海报墙数据（支持分页）"""
    global last_result, db
    
    # 优先使用内存中的检测结果
    if last_result is not None:
        all_cards = detector.get_card_data(last_result)
    elif db is not None:
        # 从数据库加载最新的检测结果
        latest = db.get_latest_detection_result(limit=1)
        if latest and latest[0].get('missing_details'):
            # 转换为卡片格式
            all_cards = []
            for detail in latest[0]['missing_details']:
                card = {
                    'series_id': detail['series_id'],
                    'series_name': detail['series_name'],
                    'season': detail['season_number'],
                    'missing_episodes': detail['episode_numbers'],
                    'missing_count': len(detail['episode_numbers']),
                    'year': detail.get('year', ''),
                    'status': detail.get('status', 'ongoing'),
                    'poster_url': detail.get('poster_url', ''),
                    'tmdb_id': detail.get('tmdb_id'),  # 使用数据库中的 TMDB ID
                    'total_seasons': 0
                }
                all_cards.append(card)
        else:
            all_cards = []
    else:
        all_cards = []
    
    if not all_cards:
        return {
            "status": "no_data",
            "message": "暂无检测结果，请先运行检测",
            "cards": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
                "has_more": False
            }
        }
    
    total = len(all_cards)
    
    # 计算分页
    start = (page - 1) * page_size
    end = start + page_size
    page_cards = all_cards[start:end]
    
    return {
        "status": "success",
        "cards": page_cards,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "has_more": end < total
        }
    }


@app.get("/api/health")
async def health_check(current_user: Dict[str, Any] = Depends(get_current_user)):
    """健康检查"""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/history")
async def get_history(limit: int = 20):
    """获取检测历史"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化"}
    history = db.get_detection_history(limit)
    return {"status": "success", "history": history}


@app.get("/api/statistics")
async def get_statistics():
    """获取统计信息"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化"}
    stats = db.get_statistics()
    return {"status": "success", "statistics": stats}


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    if detection_scheduler is None:
        return {"status": "not_started", "message": "调度器未启动"}
    return {"status": "success", "scheduler": detection_scheduler.get_status()}


@app.post("/api/export/csv")
async def export_csv():
    """导出 CSV"""
    import os
    if db is None or exporter is None:
        raise HTTPException(status_code=400, detail="服务未初始化")
    data = db.get_latest_missing_episodes()
    filename = exporter.export_to_csv(data)
    return {"status": "success", "filename": os.path.basename(filename), "records": len(data)}


@app.post("/api/export/excel")
async def export_excel():
    """导出 Excel"""
    import os
    if db is None or exporter is None:
        raise HTTPException(status_code=400, detail="服务未初始化")
    data = db.get_latest_missing_episodes()
    filename = exporter.export_to_excel(data)
    if filename:
        return {"status": "success", "filename": os.path.basename(filename), "records": len(data)}
    raise HTTPException(status_code=500, detail="Excel 导出失败")


# ============ MoviePilot 下载 API ============

class DownloadRequest(BaseModel):
    """下载请求"""
    series_id: str
    series_name: str
    season: int
    episodes: List[int] = []


@app.post("/api/download")
async def push_download(request: DownloadRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """推送缺失剧集到 MoviePilot 下载"""
    global db, config_manager
    
    if config_manager is None:
        config_manager = get_config_manager()
    
    # 获取 MoviePilot 配置
    mp_config = config_manager.get_moviepilot_config()
    if not mp_config.get('enabled') or not mp_config.get('host'):
        raise HTTPException(status_code=400, detail="MoviePilot 未配置")
    
    # 确保数据库已初始化（移到 try 块之前）
    if db is None:
        from app.database import get_database
        db = get_database()
        logger.info("初始化数据库实例")
    
    # 调用 MoviePilot API
    api_success = False
    subscribe_id = None
    
    try:
        # 初始化 MoviePilot 客户端（每次重新获取 token）
        from app.moviepilot_client import MoviePilotClient
        mp_client = MoviePilotClient(
            mp_config['host'],
            mp_config.get('username', 'admin'),
            mp_config.get('password', '')
        )
        
        # 订阅剧集（MoviePilot 会自动识别已有集数，只下载缺失的）
        result = mp_client.subscribe_tv(
            title=request.series_name,
            season=request.season,
        )
        
        # MoviePilot 返回格式：{"success":true,"data":{"id":110}}
        if result:
            subscribe_id = result.get('id')
            if result.get('data') and result['data'].get('id'):
                subscribe_id = result['data'].get('id')
            api_success = result.get('success', False)
            
    except Exception as e:
        logger.error(f"MoviePilot API 调用失败：{e}")
        api_success = False
    
    # 无论 API 成功失败都保存记录（用于前端显示状态）- 移到 try 块之外
    status = 'completed' if (subscribe_id or api_success) else 'failed'
    
    record_id = db.save_download_history(
        series_id=request.series_id,
        series_name=request.series_name,
        season_number=request.season,
        episode_numbers=request.episodes,
        moviepilot_task_id=str(subscribe_id) if subscribe_id else None,
        status=status
    )
    
    logger.info(f"下载记录已保存：record_id={record_id}, status={status}")
    
    if status == 'completed':
        return {
            "status": "success",
            "message": f"已推送 {request.series_name} S{request.season} 到 MoviePilot",
            "subscribe_id": subscribe_id,
            "record_id": record_id
        }
    else:
        # 保存了失败记录，但返回错误
        raise HTTPException(status_code=500, detail="MoviePilot 订阅失败")


@app.get("/api/download/history")
async def get_download_history(status: Optional[str] = None, limit: int = 100):
    """获取下载历史"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化"}
    
    history = db.get_download_history(status=status, limit=limit)
    return {
        "status": "success",
        "history": history,
        "total": len(history)
    }


@app.get("/api/download/status/{series_id}")
async def get_download_status(series_id: str):
    """获取指定剧集的下载状态"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化"}
    
    history = db.get_download_history(series_id=series_id, limit=10)
    
    # 统计各状态数量
    status_count = {}
    for record in history:
        status = record.get('status', 'unknown')
        status_count[status] = status_count.get(status, 0) + 1
    
    return {
        "status": "success",
        "series_id": series_id,
        "history": history,
        "status_summary": status_count
    }


@app.get("/api/last-detection")
async def get_last_detection():
    """获取最近一次的检测结果（从数据库加载）"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化"}
    
    results = db.get_latest_detection_result(limit=1)
    
    if not results:
        return {"status": "no_data", "message": "暂无检测结果"}
    
    latest = results[0]
    
    # 获取所有已下载的 series_id
    downloaded_series = set()
    if db:
        history = db.get_download_history(limit=1000)
        for record in history:
            if record.get('status') == 'completed':
                downloaded_series.add(record.get('series_id'))
    
    # 转换为卡片数据格式
    cards_map = {}
    for detail in latest.get('missing_details', []):
        series_id = detail['series_id']
        if series_id not in cards_map:
            cards_map[series_id] = {
                'series_id': series_id,
                'series_name': detail['series_name'],
                'missing_count': 0,
                'total_seasons': 0,
                'seasons': [],
                'year': detail.get('year', ''),
                'status': detail.get('status', 'ongoing'),
                'poster': detail.get('poster_url', ''),
                'tmdb_id': None,
                'download_status': 'completed' if series_id in downloaded_series else 'pending'
            }
        
        # 添加该季的缺失信息
        season_num = detail['season_number']
        eps = detail['episode_numbers']
        cards_map[series_id]['seasons'].append({
            'season_number': season_num,
            'missing_episodes': eps
        })
        cards_map[series_id]['missing_count'] += len(eps)
        cards_map[series_id]['total_seasons'] = max(
            cards_map[series_id]['total_seasons'], 
            season_num
        )
    
    # 转换为列表并按缺失集数排序
    cards = list(cards_map.values())
    cards.sort(key=lambda x: x['missing_count'], reverse=True)
    
    return {
        "status": "success",
        "detection_time": latest.get('detection_time'),
        "stats": {
            "total_series": latest.get('total_series', 0),
            "series_with_missing": len(cards),
            "total_missing_episodes": latest.get('total_missing_episodes', 0)
        },
        "cards": cards,
        "from_cache": True
    }


# ============ HDHive API ============

@app.get("/api/hdhive/config")
async def get_hdhive_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取 HDHive 配置"""
    global config_manager
    if config_manager is None:
        config_manager = get_config_manager()
    
    config = config_manager.get_hdhive_config()
    # 隐藏敏感信息
    safe_config = {
        "enabled": config.get("enabled", False),
        "api_key": _mask_secret(config.get("api_key", "")),
        "base_url": config.get("base_url", "https://hdhive.com/api/open"),
        "proxy": {
            "enabled": config.get("proxy", {}).get("enabled", False),
            "host": config.get("proxy", {}).get("host", ""),
            "port": config.get("proxy", {}).get("port", 0),
            "username": config.get("proxy", {}).get("username", ""),
            "has_auth": bool(config.get("proxy", {}).get("username"))
        },
        "settings": config.get("settings", {})
    }
    
    return {"status": "success", "config": safe_config}


@app.post("/api/hdhive/config")
async def set_hdhive_config(config: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """设置 HDHive 配置"""
    global config_manager
    
    if config_manager is None:
        config_manager = get_config_manager()
    
    existing_config = config_manager.get_hdhive_config()
    api_key = config.get("api_key", "")
    if api_key == MASKED_SECRET:
        api_key = existing_config.get("api_key", "")

    proxy_config = config.get("proxy") or {}
    existing_proxy = existing_config.get("proxy", {})
    proxy_password = proxy_config.get("password", "")
    if proxy_password == MASKED_SECRET or proxy_password == "":
        proxy_password = existing_proxy.get("password", "")
    
    success = config_manager.set_hdhive_config(
        api_key=api_key,
        base_url=config.get("base_url", "https://hdhive.com/api/open"),
        enabled=config.get("enabled", False),
        proxy={
            "enabled": proxy_config.get("enabled", False),
            "host": proxy_config.get("host", ""),
            "port": proxy_config.get("port", 0),
            "username": proxy_config.get("username", ""),
            "password": proxy_password
        },
        settings=config.get("settings")
    )
    
    if success:
        full_config = config_manager.get_all_config()
        _apply_runtime_config(full_config)
        
        test_result = None
        hdhive_config = full_config.get("hdhive", {})
        if hdhive_config.get("enabled") and api_key:
            try:
                if hdhive_client is not None:
                    hdhive_client.ping()
                test_result = "连接成功"
            except Exception as e:
                test_result = f"连接失败: {str(e)}"
        
        return {
            "status": "success",
            "message": "配置保存成功",
            "test_result": test_result
        }
    else:
        raise HTTPException(status_code=500, detail="配置保存失败")


@app.get("/api/hdhive/status")
async def get_hdhive_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取 HDHive 状态（积分余额、配额等）"""
    global config_manager
    if config_manager is None:
        config_manager = get_config_manager()
    if hdhive_client is None:
        return {"status": "not_configured", "message": "HDHive 未配置"}
    
    try:
        # 获取用户信息
        user_info = hdhive_client.get_user_info()
        quota = hdhive_client.get_quota()
        
        return {
            "status": "success",
            "user": {
                "nickname": user_info.get("nickname", ""),
                "is_vip": user_info.get("is_vip", False),
                "points": user_info.get("user_meta", {}).get("points", 0)
            },
            "quota": {
                "daily_reset": quota.get("daily_reset"),
                "endpoint_limit": quota.get("endpoint_limit"),
                "endpoint_remaining": quota.get("endpoint_remaining")
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/hdhive/search")
async def search_hdhive_resources(series_id: str = None, tmdb_id: str = None, season: int = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    搜索 HDHive 资源
    
    Args:
        series_id: Emby 剧集 ID（可选，当 tmdb_id 为空时用于获取 TMDB ID）
        tmdb_id: TMDB ID（可选，当 series_id 提供时自动获取）
        season: 季号（可选）
    """
    global config_manager, emby_client
    if config_manager is None:
        config_manager = get_config_manager()
    if hdhive_client is None:
        raise HTTPException(status_code=400, detail="HDHive 未配置")
    
    # 如果没有 tmdb_id 但有 series_id，尝试从 Emby 获取
    if not tmdb_id and series_id:
        try:
            tmdb_id = emby_client.get_tmdb_id(series_id)
            logger.info(f"从 Emby 获取 TMDB ID: {series_id} -> {tmdb_id}")
        except Exception as e:
            logger.warning(f"从 Emby 获取 TMDB ID 失败：{e}")
    
    if not tmdb_id:
        raise HTTPException(status_code=400, detail="无法获取 TMDB ID，请检查剧集刮削信息或先运行检测获取 TMDB 数据")
    
    try:
        # 搜索资源
        resources = hdhive_client.search_tv_resources(
            tmdb_id=tmdb_id,
            season=season,
            prefer_115=config_manager.get_hdhive_config().get("settings", {}).get("prefer_115", True)
        )
        
        # 过滤资源（只返回包含所需信息的）
        result = []
        for r in resources:
            result.append({
                "slug": r.get("slug"),
                "title": r.get("title"),
                "share_size": r.get("share_size"),
                "video_resolution": r.get("video_resolution", []),
                "source": r.get("source", []),
                "subtitle_language": r.get("subtitle_language", []),
                "unlock_points": r.get("unlock_points") or 0,
                "is_unlocked": r.get("is_unlocked", False),
                "validate_status": r.get("validate_status"),
                "is_official": r.get("is_official", False),
                "pan_type": r.get("pan_type")  # 添加网盘类型字段
            })
        
        return {
            "status": "success",
            "tmdb_id": tmdb_id,
            "total": len(result),
            "resources": result
        }
    except Exception as e:
        logger.error(f"搜索 HDHive 资源失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hdhive/unlock")
async def unlock_hdhive_resource(data: Dict[str, str], current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    解锁 HDHive 资源
    
    Args:
        data: {"slug": "资源标识"}
    """
    if hdhive_client is None:
        raise HTTPException(status_code=400, detail="HDHive 未配置")
    
    slug = data.get("slug")
    if not slug:
        raise HTTPException(status_code=400, detail="缺少资源标识")
    
    try:
        # 解锁资源
        result = hdhive_client.unlock_resource(slug)
        
        # 保存解锁记录到数据库
        if db and result.get("url"):
            db.save_hdhive_unlock(
                slug=slug,
                url=result.get("url"),
                access_code=result.get("access_code", ""),
                points_spent=result.get("points_spent", 0)
            )
        
        return {
            "status": "success",
            "message": "解锁成功" if not result.get("already_owned") else "已拥有该资源",
            "data": result
        }
    except Exception as e:
        logger.error(f"解锁资源失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hdhive/history")
async def get_hdhive_unlock_history(limit: int = 20, current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取 HDHive 解锁历史"""
    if db is None:
        return {"status": "no_db", "message": "数据库未初始化", "history": []}
    
    try:
        history = db.get_hdhive_unlocks(limit)
        return {"status": "success", "history": history}
    except Exception as e:
        return {"status": "error", "message": str(e), "history": []}


# ============ 企业微信 API ============

@app.get("/api/wecom/config")
async def get_wecom_config(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取企业微信配置"""
    global config_manager
    if config_manager is None:
        config_manager = get_config_manager()

    config = config_manager.get_wecom_config()
    safe_config = {
        "enabled": config.get("enabled", False),
        "corp_id": config.get("corp_id", ""),
        "agent_id": config.get("agent_id", 0),
        "corp_secret": _mask_secret(config.get("corp_secret", "")),
        "token": _mask_secret(config.get("token", "")),
        "encoding_aes_key": _mask_secret(config.get("encoding_aes_key", "")),
        "base_url": config.get("base_url", "https://qyapi.weixin.qq.com/cgi-bin")
    }
    return {"status": "success", "config": safe_config}


@app.post("/api/wecom/config")
async def set_wecom_config(config: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """设置企业微信配置"""
    global config_manager

    if config_manager is None:
        config_manager = get_config_manager()

    existing_config = config_manager.get_wecom_config()

    corp_secret = config.get("corp_secret", "")
    if corp_secret == MASKED_SECRET:
        corp_secret = existing_config.get("corp_secret", "")

    token = config.get("token", "")
    if token == MASKED_SECRET:
        token = existing_config.get("token", "")

    encoding_aes_key = config.get("encoding_aes_key", "")
    if encoding_aes_key == MASKED_SECRET:
        encoding_aes_key = existing_config.get("encoding_aes_key", "")

    success = config_manager.set_wecom_config(
        enabled=config.get("enabled", False),
        corp_id=config.get("corp_id", ""),
        agent_id=int(config.get("agent_id", 0) or 0),
        corp_secret=corp_secret,
        token=token,
        encoding_aes_key=encoding_aes_key,
        base_url=config.get("base_url", "https://qyapi.weixin.qq.com/cgi-bin"),
    )

    if not success:
        raise HTTPException(status_code=500, detail="配置保存失败")

    full_config = config_manager.get_all_config()
    _apply_runtime_config(full_config)

    test_result = None
    if full_config.get("wecom", {}).get("enabled") and wecom_client is not None:
        try:
            if wecom_client.can_send():
                wecom_client.get_access_token()
                test_result = "AccessToken 获取成功"
            elif wecom_client.can_callback():
                test_result = "回调模式配置成功"
            else:
                test_result = "已保存，但主动发送和回调参数都不完整"
        except Exception as exc:
            test_result = f"连接失败: {exc}"

    return {
        "status": "success",
        "message": "企业微信配置保存成功",
        "test_result": test_result
    }


@app.get("/api/wecom/status")
async def get_wecom_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取企业微信状态"""
    global config_manager
    if config_manager is None:
        config_manager = get_config_manager()

    if wecom_client is None:
        return {"status": "not_configured", "message": "企业微信未配置"}

    try:
        result = {
            "status": "success",
            "callback_ready": wecom_client.can_callback(),
            "send_ready": wecom_client.can_send(),
        }
        if wecom_client.can_send():
            wecom_client.get_access_token()
            result["message"] = "企业微信连接正常"
        else:
            result["message"] = "企业微信回调模式已启用"
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/api/wecom/callback")
async def verify_wecom_callback(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
):
    """企业微信回调 URL 验证"""
    if wecom_client is None:
        raise HTTPException(status_code=400, detail="企业微信未配置")

    try:
        echo = wecom_client.verify_callback_url(msg_signature, timestamp, nonce, echostr)
        logger.info("企业微信 URL 验证成功")
        return Response(content=echo, media_type="text/plain")
    except Exception as exc:
        logger.error(f"企业微信 URL 验证失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/wecom/callback")
async def receive_wecom_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: Optional[str] = None,
    timestamp: Optional[str] = None,
    nonce: Optional[str] = None,
):
    """接收企业微信消息并处理命令"""
    global config_manager
    if wecom_client is None:
        raise HTTPException(status_code=400, detail="企业微信未配置")
    if config_manager is None:
        config_manager = get_config_manager()

    body = (await request.body()).decode("utf-8")
    dedupe_key = ""
    logger.info(
        "收到企业微信回调: body_length={}, encrypted={}",
        len(body),
        "yes" if "<Encrypt>" in body else "no",
    )

    try:
        message = wecom_client.parse_callback_message(
            body,
            msg_signature,
            timestamp,
            nonce,
            require_encrypted=True,
        )
        msg_type = (message.get("MsgType") or "").lower()
        from_user = message.get("FromUserName", "")
        to_user = message.get("ToUserName", "")
        current_db = db
        current_tmdb_client = tmdb_client
        current_hdhive_client = hdhive_client
        current_config_manager = config_manager
        current_wecom_client = wecom_client
        dedupe_key = _build_wecom_message_key(message)

        if current_db is not None:
            reserved = current_db.reserve_wecom_message(
                dedupe_key=dedupe_key,
                user_id=from_user,
                msg_type=msg_type,
                msg_id=str(message.get("MsgId") or message.get("MsgId64") or ""),
                content=str(message.get("Content") or message.get("Event") or ""),
            )
            if not reserved.get("created"):
                record = reserved.get("record") or {}
                logger.info(
                    "企业微信重复消息已拦截: dedupe_key={}, status={}",
                    dedupe_key,
                    record.get("status", "unknown"),
                )
                if current_wecom_client.can_send():
                    return Response(content="success", media_type="text/plain")

                cached_reply = record.get("response_text") or "请求已接收，正在处理。"
                reply_xml = current_wecom_client.build_text_reply(
                    to_user=from_user,
                    from_user=to_user,
                    content=cached_reply,
                    timestamp=timestamp,
                    nonce=nonce,
                )
                return Response(content=reply_xml, media_type="application/xml")

        logger.info(
            "企业微信消息解析完成: msg_type={}, from_user={}, dedupe_key={}",
            msg_type or "unknown",
            from_user or "unknown",
            dedupe_key,
        )

        if current_wecom_client.can_send():
            background_tasks.add_task(
                _process_wecom_message_async,
                dedupe_key,
                message,
                current_wecom_client,
                current_tmdb_client,
                current_hdhive_client,
                current_db,
                current_config_manager,
            )
            logger.info(
                "企业微信消息已切换为异步处理: msg_type={}, from_user={}",
                msg_type or "unknown",
                from_user or "unknown",
            )
            return Response(content="success", media_type="text/plain")

        reply_text = _build_wecom_reply_text(
            message=message,
            current_tmdb_client=current_tmdb_client,
            current_hdhive_client=current_hdhive_client,
            current_db=current_db,
            current_config_manager=current_config_manager,
        )
        if current_db is not None:
            current_db.complete_wecom_message(dedupe_key, reply_text, "sync")

        reply_xml = current_wecom_client.build_text_reply(
            to_user=from_user,
            from_user=to_user,
            content=reply_text,
            timestamp=timestamp,
            nonce=nonce,
        )
        logger.info(
            "企业微信回调处理完成: msg_type={}, from_user={}, reply_length={}",
            msg_type or "unknown",
            from_user or "unknown",
            len(reply_text),
        )
        return Response(content=reply_xml, media_type="application/xml")
    except Exception as exc:
        if dedupe_key and db is not None:
            try:
                db.fail_wecom_message(dedupe_key, str(exc))
            except Exception as db_exc:
                logger.warning(f"记录企业微信消息失败状态时出错: {db_exc}")
        logger.error(f"企业微信回调处理失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


# ============ 静态文件 ============

# 挂载静态文件目录
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ============ HTML 页面 ============

def get_html_content():
    """生成 HTML 页面（旧版，兼容用）"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Emby 缺集检测系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .status-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .status-row:last-child { border-bottom: none; }
        .status-label { color: #666; }
        .status-value { font-weight: 600; color: #333; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover { opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .result-box {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        .config-form {
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #666;
        }
        .form-group input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 Emby 缺集检测系统</h1>
        <p class="subtitle">参考 MoviePilot 设计 · 自动检测媒体库缺失剧集</p>
        
        <div class="config-form" id="configForm">
            <div class="form-group">
                <label>Emby 服务器地址</label>
                <input type="text" id="embyHost" placeholder="http://localhost:8096">
            </div>
            <div class="form-group">
                <label>API 密钥</label>
                <input type="password" id="embyApiKey" placeholder="请输入 API 密钥">
            </div>
            <button class="btn" onclick="saveConfig()">保存配置</button>
        </div>
        
        <div class="status-card">
            <div class="status-row">
                <span class="status-label">连接状态</span>
                <span class="status-value" id="statusValue">未配置</span>
            </div>
            <div class="status-row">
                <span class="status-label">剧集总数</span>
                <span class="status-value" id="totalSeries">-</span>
            </div>
            <div class="status-row">
                <span class="status-label">有缺集的剧集</span>
                <span class="status-value" id="missingSeries">-</span>
            </div>
            <div class="status-row">
                <span class="status-label">缺失总集数</span>
                <span class="status-value" id="totalMissing">-</span>
            </div>
        </div>
        
        <button class="btn" id="detectBtn" onclick="runDetection()" disabled>
            🔍 开始检测
        </button>
        
        <div class="result-box" id="resultBox">
            <div class="loading">点击"开始检测"查看结果</div>
        </div>
    </div>
    
    <script>
        async function saveConfig() {
            const host = document.getElementById('embyHost').value;
            const apiKey = document.getElementById('embyApiKey').value;
            
            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({host, api_key: apiKey})
                });
                const data = await res.json();
                alert(data.message);
                if (data.status === 'success') {
                    document.getElementById('statusValue').textContent = '已连接';
                    document.getElementById('detectBtn').disabled = false;
                }
            } catch (e) {
                alert('配置失败：' + e.message);
            }
        }
        
        async function runDetection() {
            const btn = document.getElementById('detectBtn');
            const resultBox = document.getElementById('resultBox');
            
            btn.disabled = true;
            btn.textContent = '检测中...';
            resultBox.innerHTML = '<div class="loading">正在分析媒体库...</div>';
            
            try {
                const res = await fetch('/api/detect');
                const data = await res.json();
                
                if (data.status === 'success') {
                    resultBox.textContent = data.summary;
                    document.getElementById('totalSeries').textContent = data.stats.total_series;
                    document.getElementById('missingSeries').textContent = data.stats.series_with_missing;
                    document.getElementById('totalMissing').textContent = data.stats.total_missing_episodes;
                }
            } catch (e) {
                resultBox.textContent = '检测失败：' + e.message;
            }
            
            btn.disabled = false;
            btn.textContent = '🔍 开始检测';
        }
        
        // 检查状态
        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('statusValue').textContent = 
                    data.status === 'connected' ? '已连接' : 
                    data.status === 'disconnected' ? '连接失败' : '未配置';
                if (data.status === 'connected') {
                    document.getElementById('detectBtn').disabled = false;
                }
            } catch (e) {
                console.error('状态检查失败:', e);
            }
        }
        
        checkStatus();
    </script>
</body>
</html>
'''


# ============ 主程序 ============

if __name__ == "__main__":
    logger.info("启动 Emby 缺集检测系统...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
