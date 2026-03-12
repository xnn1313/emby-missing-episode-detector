"""
Emby 缺集检测系统 - 主程序入口
参考 MoviePilot 设计，基于 FastAPI
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Any
from loguru import logger
import uvicorn

from app.emby_client import EmbyClient
from app.detector import MissingEpisodeDetector
from app.tmdb_client import TMDBClient, TMDBMatcher
from app.notifier import setup_notifiers_from_env, NotificationManager
from app.telegram_notifier import setup_telegram_from_env, TelegramNotifier
from app.scheduler import DetectionScheduler
from app.database import get_database, Database
from app.export import ReportExporter
from app.config_manager import get_config_manager, ConfigManager

# 配置日志
logger.remove()
logger.add(
    project_root / "logs" / "emby-detector.log",
    level="INFO",
    rotation="100 MB",
    retention="7 days"
)
logger.add(sys.stdout, level="INFO")

# 创建 FastAPI 应用
app = FastAPI(
    title="Emby 缺集检测系统",
    description="基于 MoviePilot 设计理念的 Emby 媒体库缺集检测工具",
    version="0.1.0"
)

# 全局变量
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
last_result = None


# ============ 数据模型 ============

class EmbyConfig(BaseModel):
    """Emby 配置"""
    host: str
    api_key: str


class LibraryConfig(BaseModel):
    """媒体库配置"""
    enabled: bool = False
    selected_ids: List[str] = []


class MoviePilotConfig(BaseModel):
    """MoviePilot 配置"""
    host: str = ""
    username: str = "admin"
    password: str = ""
    enabled: bool = False
    auto_download: bool = True
    download_path: str = ""


class FullConfig(BaseModel):
    """完整配置"""
    host: Optional[str] = None
    api_key: Optional[str] = None
    libraries: Optional[LibraryConfig] = None
    tmdb_api_key: Optional[str] = None
    detection_interval: Optional[int] = None
    moviepilot: Optional[MoviePilotConfig] = None


class DetectionStatus(BaseModel):
    """检测状态"""
    status: str
    message: str
    total_series: int = 0
    series_with_missing: int = 0
    total_missing: int = 0


class MissingEpisode(BaseModel):
    """缺失的集"""
    series_name: str
    season: int
    episodes: List[int]


# ============ API 路由 ============

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页 - 重定向到海报墙"""
    from fastapi.responses import FileResponse
    return FileResponse(static_path / "index.html")


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
async def get_libraries():
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
async def get_config():
    """获取当前配置"""
    global config_manager
    
    if config_manager is None:
        config_manager = get_config_manager()
    
    config = config_manager.get_all_config()
    
    return {
        "status": "success",
        "config": {
            "emby": config.get("emby", {}),
            "libraries": config.get("libraries", {}),
            "tmdb": config.get("tmdb", {}),
            "detection": config.get("detection", {}),
            "moviepilot": config.get("moviepilot", {})
        }
    }


@app.post("/api/config")
async def set_config(config: FullConfig):
    """设置完整配置（支持媒体库配置）"""
    global emby_client, detector, notifier_manager, db, exporter, detection_scheduler, config_manager, last_result, moviepilot_client
    
    try:
        # 初始化配置管理器
        config_manager = get_config_manager()
        
        # 保存 MoviePilot 配置（优先保存，确保持久化）
        if config.moviepilot:
            config_manager.set_moviepilot_config(
                host=config.moviepilot.host or "",
                username=config.moviepilot.username or "admin",
                password=config.moviepilot.password or "",
                enabled=config.moviepilot.enabled,
                auto_download=config.moviepilot.auto_download,
                download_path=config.moviepilot.download_path or ""
            )
            logger.info(f"MoviePilot 配置已保存：{config.moviepilot.host}")
        
        # 设置 Emby 配置
        if config.host and config.api_key:
            config_manager.set_emby_config(config.host, config.api_key)
            emby_client = EmbyClient(config.host, config.api_key)
        
        # 设置媒体库配置
        if config.libraries:
            config_manager.set_library_config(
                config.libraries.enabled,
                config.libraries.selected_ids
            )
        
        # 设置 TMDB 配置
        if config.tmdb_api_key:
            config_manager.set_tmdb_config(config.tmdb_api_key)
        
        # 设置检测间隔
        if config.detection_interval:
            config_manager.set_detection_interval(config.detection_interval)
        
        # 设置 MoviePilot 配置
        if config.moviepilot:
            config_manager.set_moviepilot_config(
                host=config.moviepilot.host,
                username=config.moviepilot.username or "admin",
                password=config.moviepilot.password or "",
                enabled=config.moviepilot.enabled,
                auto_download=config.moviepilot.auto_download,
                download_path=config.moviepilot.download_path or ""
            )
        
        # 初始化其他组件
        if emby_client:
            # 获取媒体库配置
            lib_config = config_manager.get_library_config()
            library_ids = lib_config.get('selected_ids', []) if lib_config.get('enabled') else None
            
            # 初始化检测器（带媒体库过滤）
            detector = MissingEpisodeDetector(library_ids=library_ids)
            notifier_manager = setup_notifiers_from_env()
            db = get_database()
            exporter = ReportExporter()
            
            # 获取检测间隔配置
            detection_config = config_manager.get_detection_config()
            interval = detection_config.get('interval_minutes', 60)
            
            # 启动定时检测
            detection_scheduler = DetectionScheduler(emby_client, detector, notifier_manager)
            detection_scheduler.start_auto_detection(interval_minutes=interval)
            
            # 清空上次结果
            last_result = None
            
            if emby_client.test_connection():
                return {
                    "status": "success",
                    "message": "配置成功，Emby 连接正常",
                    "scheduler": f"定时检测已启动 (每{interval}分钟)",
                    "library_filter": f"{'启用' if library_ids else '禁用'} ({len(library_ids) if library_ids else 0}个库)"
                }
            else:
                return {"status": "error", "message": "Emby 连接失败，请检查配置"}
        else:
            return {"status": "error", "message": "Emby 配置不完整"}
    except Exception as e:
        logger.error(f"配置失败：{e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/detect")
async def run_detection():
    """运行缺集检测"""
    global last_result
    
    if emby_client is None:
        raise HTTPException(status_code=400, detail="Emby 未配置")
    
    if detector is None:
        raise HTTPException(status_code=400, detail="检测器未初始化")
    
    try:
        logger.info("开始手动检测...")
        last_result = detector.detect(emby_client)
        
        # 保存到数据库
        if db:
            db.save_detection_result(last_result)
        
        # 发送通知
        if notifier_manager and last_result.series_with_missing > 0:
            notifier_manager.send_missing_report(last_result)
        
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
    except Exception as e:
        logger.error(f"检测失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results")
async def get_results():
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


@app.get("/api/cards")
async def get_cards():
    """获取海报墙数据"""
    global last_result
    if last_result is None:
        return {"status": "no_data", "message": "暂无检测结果"}
    cards = detector.get_card_data(last_result)
    return {"status": "success", "cards": cards}


@app.get("/api/health")
async def health_check():
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
async def push_download(request: DownloadRequest):
    """推送缺失剧集到 MoviePilot 下载"""
    global moviepilot_client, db, config_manager
    
    if config_manager is None:
        config_manager = get_config_manager()
    
    # 获取 MoviePilot 配置
    mp_config = config_manager.get_moviepilot_config()
    if not mp_config.get('enabled') or not mp_config.get('host'):
        raise HTTPException(status_code=400, detail="MoviePilot 未配置")
    
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
        subscribe_id = None
        if result:
            subscribe_id = result.get('id')
            if result.get('data') and result['data'].get('id'):
                subscribe_id = result['data'].get('id')
        
        if subscribe_id or (result and result.get('success')):
            # 保存下载历史
            subscribe_id = result.get('id') or result['data'].get('id')
            
            # 确保数据库已初始化
            if db is None:
                from app.database import get_database
                db = get_database()
            
            record_id = db.save_download_history(
                series_id=request.series_id,
                series_name=request.series_name,
                season_number=request.season,
                episode_numbers=request.episodes,
                moviepilot_task_id=str(result.get('id'))
            )
            
            return {
                "status": "success",
                "message": f"已推送 {request.series_name} S{request.season} 到 MoviePilot",
                "subscribe_id": result.get('id'),
                "record_id": record_id
            }
        else:
            raise HTTPException(status_code=500, detail="MoviePilot 订阅失败")
            
    except Exception as e:
        logger.error(f"推送下载失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                'year': '',
                'status': 'ongoing',
                'poster': '',
                'tmdb_id': None
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
