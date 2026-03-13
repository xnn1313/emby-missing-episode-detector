"""
缺集检测逻辑模块 - 集成 TMDB 对比
分析剧集数据，识别缺失的集数（基于 TMDB 标准）
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

try:
    from app.tmdb_client import TMDBMatcher
    TMDB_AVAILABLE = True
except ImportError:
    TMDB_AVAILABLE = False
    logger.warning("TMDB 模块不可用，将使用基础检测模式")


@dataclass
class EpisodeInfo:
    """集信息"""
    episode_number: int
    episode_id: str
    episode_name: str
    air_date: Optional[str]
    has_media: bool


@dataclass
class SeasonInfo:
    """季信息"""
    season_number: int
    season_id: str
    season_name: str
    episodes: List[EpisodeInfo] = field(default_factory=list)
    missing_episodes: List[int] = field(default_factory=list)
    expected_episodes: int = 0


@dataclass
class SeriesInfo:
    """剧集信息"""
    series_id: str
    series_name: str
    series_path: str
    tmdb_id: Optional[int] = None
    seasons: List[SeasonInfo] = field(default_factory=list)
    total_seasons: int = 0
    total_episodes: int = 0
    missing_episodes_count: int = 0
    status: str = "ongoing"  # ongoing, ended
    poster_url: Optional[str] = None
    year: Optional[str] = None


@dataclass
class DetectionResult:
    """检测结果"""
    series: List[SeriesInfo] = field(default_factory=list)
    total_series: int = 0
    series_with_missing: int = 0
    total_missing_episodes: int = 0
    detection_time: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    use_tmdb: bool = False


class MissingEpisodeDetector:
    """缺集检测器 - 支持 TMDB 对比和媒体库过滤"""
    
    def __init__(self, tmdb_matcher: Optional[TMDBMatcher] = None, library_ids: Optional[List[str]] = None):
        """
        初始化检测器
        
        Args:
            tmdb_matcher: TMDB 匹配器（可选）
            library_ids: 要检测的媒体库 ID 列表，None 表示检测所有库
        """
        self.tmdb_matcher = tmdb_matcher
        self.use_tmdb = tmdb_matcher is not None and TMDB_AVAILABLE
        self.library_ids = library_ids
        self.use_library_filter = library_ids is not None and len(library_ids) > 0
        logger.info(f"缺集检测器已初始化 (TMDB: {'启用' if self.use_tmdb else '禁用'}, 媒体库过滤：{'启用' if self.use_library_filter else '禁用'})")
    
    def detect(self, emby_client) -> DetectionResult:
        """
        执行缺集检测
        
        Args:
            emby_client: EmbyClient 实例
        
        Returns:
            DetectionResult 检测结果
        """
        import time
        start_time = time.time()
        
        logger.info("开始缺集检测...")
        result = DetectionResult(use_tmdb=self.use_tmdb)
        
        # 获取所有剧集（支持媒体库过滤）
        tv_shows = emby_client.get_tv_shows(library_ids=self.library_ids)
        result.total_series = len(tv_shows)
        logger.info(f"发现 {len(tv_shows)} 个剧集")
        
        # 按剧集逐个分析（Emby 数据量大时批量获取不可行）
        # 优化：使用 _analyze_series 直接调用 API，但只获取必要字段
        logger.info(f"开始逐个分析 {len(tv_shows)} 个剧集...")
        processed = 0
        for show in tv_shows:
            series_info = self._analyze_series(show, emby_client)
            processed += 1
            # 更频繁的进度日志（每 100 个）
            if processed % 100 == 0:
                elapsed = time.time() - start_time
                eta = (elapsed / processed * len(tv_shows) - elapsed) / 60 if processed > 0 else 0
                logger.info(f"进度：{processed}/{len(tv_shows)} ({processed*100//len(tv_shows)}%) | 已用：{elapsed:.0f}s | 预计剩余：{eta:.1f}分钟")
            if series_info:
                result.series.append(series_info)
                if series_info.missing_episodes_count > 0:
                    result.series_with_missing += 1
                    result.total_missing_episodes += series_info.missing_episodes_count
        
        logger.info(f"剧集分析完成：{processed} 个")
        
        result.detection_time = datetime.now()
        result.duration_seconds = time.time() - start_time
        
        logger.info(
            f"检测完成：{result.series_with_missing}/{result.total_series} "
            f"个剧集有缺集，共缺失 {result.total_missing_episodes} 集，"
            f"耗时 {result.duration_seconds:.2f}秒"
        )
        
        return result
    
    def _analyze_series_optimized(self, show: Dict, emby_client, episodes_by_series: Dict) -> Optional[SeriesInfo]:
        """分析单个剧集（优化版本，使用批量获取的集数据）"""
        try:
            series_id = show.get('Id')
            series_name = show.get('Name', 'Unknown')
            series_path = show.get('Path', '')
            
            # 获取 TMDB 信息
            tmdb_id = None
            expected_episodes_map = {}
            
            if self.use_tmdb:
                tmdb_id = self.tmdb_matcher.match_series(show)
                if tmdb_id:
                    expected_episodes_map = self.tmdb_matcher.tmdb.get_all_seasons_episodes(tmdb_id)
            
            series_info = SeriesInfo(
                series_id=series_id,
                series_name=series_name,
                series_path=series_path,
                tmdb_id=tmdb_id
            )
            
            # 获取基本信息
            year = show.get('ProductionYear') or show.get('PremiereDate', '')
            if year:
                try:
                    series_info.year = str(year)[:4]
                except:
                    pass
            
            # 获取状态
            status = show.get('Status', '')
            series_info.status = 'ended' if status == 'Ended' else 'ongoing'
            
            # 获取海报
            image_tags = show.get('ImageTags', {})
            if 'Primary' in image_tags:
                series_info.poster_url = f"{emby_client.host}/Items/{series_id}/Images/Primary?tag={image_tags['Primary']}"
            
            # 获取所有季（去重）
            seasons = emby_client.get_seasons(series_id)
            seen_season_numbers = set()
            unique_seasons = []
            
            for season in seasons:
                season_number = season.get('IndexNumber', 0)
                if season_number not in seen_season_numbers:
                    seen_season_numbers.add(season_number)
                    unique_seasons.append(season)
            
            series_info.total_seasons = len(unique_seasons)
            
            # 使用批量获取的集数据
            episodes = episodes_by_series.get(series_id, [])
            
            for season in unique_seasons:
                season_info = self._analyze_season_with_episodes(season, episodes, expected_episodes_map)
                if season_info:
                    series_info.seasons.append(season_info)
                    series_info.total_episodes += len(season_info.episodes)
                    series_info.missing_episodes_count += len(season_info.missing_episodes)
            
            return series_info
            
        except Exception as e:
            logger.error(f"分析剧集失败 {show.get('Name')}: {e}")
            return None
    
    def _analyze_series(self, show: Dict, emby_client) -> Optional[SeriesInfo]:
        """分析单个剧集（旧方法，保留兼容）"""
        try:
            series_id = show.get('Id')
            series_name = show.get('Name', 'Unknown')
            series_path = show.get('Path', '')
            
            # 获取 TMDB 信息
            tmdb_id = None
            expected_episodes_map = {}
            
            if self.use_tmdb:
                tmdb_id = self.tmdb_matcher.match_series(show)
                if tmdb_id:
                    expected_episodes_map = self.tmdb_matcher.tmdb.get_all_seasons_episodes(tmdb_id)
            
            series_info = SeriesInfo(
                series_id=series_id,
                series_name=series_name,
                series_path=series_path,
                tmdb_id=tmdb_id
            )
            
            # 获取基本信息 - 优先使用 ProductionYear
            year = show.get('ProductionYear') or show.get('PremiereDate', '')
            if year:
                try:
                    series_info.year = str(year)[:4]
                except:
                    pass
            
            # 获取状态
            status = show.get('Status', '')
            series_info.status = 'ended' if status == 'Ended' else 'ongoing'
            
            # 获取海报
            image_tags = show.get('ImageTags', {})
            if 'Primary' in image_tags:
                series_info.poster_url = f"{emby_client.host}/Items/{series_id}/Images/Primary?tag={image_tags['Primary']}"
            
            # 获取所有季（去重）
            seasons = emby_client.get_seasons(series_id)
            seen_season_numbers = set()
            unique_seasons = []
            
            for season in seasons:
                season_number = season.get('IndexNumber', 0)
                if season_number not in seen_season_numbers:
                    seen_season_numbers.add(season_number)
                    unique_seasons.append(season)
            
            series_info.total_seasons = len(unique_seasons)
            
            for season in unique_seasons:
                season_info = self._analyze_season(season, emby_client, series_id, expected_episodes_map)
                if season_info:
                    series_info.seasons.append(season_info)
                    series_info.total_episodes += len(season_info.episodes)
                    series_info.missing_episodes_count += len(season_info.missing_episodes)
            
            return series_info
            
        except Exception as e:
            logger.error(f"分析剧集失败 {show.get('Name')}: {e}")
            return None
    
    def _analyze_season_with_episodes(self, season: Dict, all_episodes: List[Dict], expected_episodes_map: Dict) -> Optional[SeasonInfo]:
        """分析某一季（使用批量获取的集数据）"""
        try:
            season_number = season.get('IndexNumber', 0)
            # 跳过特别季
            if season_number == 0:
                return None
            
            season_id = season.get('Id')
            season_name = season.get('Name', f'Season {season_number}')
            
            season_info = SeasonInfo(
                season_number=season_number,
                season_id=season_id,
                season_name=season_name
            )
            
            # 获取预期集数（如果有 TMDB 数据）
            if season_number in expected_episodes_map:
                season_info.expected_episodes = len(expected_episodes_map[season_number])
            
            # 从批量数据中筛选该季的集
            season_episodes = [ep for ep in all_episodes if ep.get('ParentIndexNumber') == season_number]
            
            # 分析缺集
            existing_episodes = set()
            
            for ep in season_episodes:
                ep_number = ep.get('IndexNumber')
                if ep_number is not None:
                    existing_episodes.add(ep_number)
                    season_info.episodes.append(EpisodeInfo(
                        episode_number=ep_number,
                        episode_id=ep.get('Id', ''),
                        episode_name=ep.get('Name', f'Episode {ep_number}'),
                        air_date=ep.get('PremiereDate', ''),
                        has_media=ep.get('HasMedia', True)
                    ))
            
            # 找出缺失的集
            if season_info.expected_episodes > 0:
                # 使用 TMDB 预期集数
                expected_eps = set(expected_episodes_map.get(season_number, []))
                for ep_num in expected_eps:
                    if ep_num not in existing_episodes:
                        season_info.missing_episodes.append(ep_num)
            else:
                # 基于现有集数估算
                if existing_episodes:
                    max_ep = max(existing_episodes)
                    for i in range(1, max_ep + 1):
                        if i not in existing_episodes:
                            season_info.missing_episodes.append(i)
            
            return season_info
            
        except Exception as e:
            logger.error(f"分析季失败 {season.get('Name')}: {e}")
            return None
    
    def _analyze_season(self, season: Dict, emby_client, series_id: str, expected_episodes_map: Dict) -> Optional[SeasonInfo]:
        """分析某一季（旧方法，保留兼容）"""
        try:
            season_number = season.get('IndexNumber', 0)
            # 跳过特别季
            if season_number == 0:
                return None
            
            season_id = season.get('Id')
            season_name = season.get('Name', f'Season {season_number}')
            
            season_info = SeasonInfo(
                season_number=season_number,
                season_id=season_id,
                season_name=season_name
            )
            
            # 获取预期集数（如果有 TMDB 数据）
            if season_number in expected_episodes_map:
                season_info.expected_episodes = len(expected_episodes_map[season_number])
            
            # 获取所有集
            episodes = emby_client.get_episodes(series_id, season_id)
            
            # 分析缺集
            existing_episodes = set()
            
            for ep in episodes:
                ep_number = ep.get('IndexNumber')
                if ep_number is not None:
                    existing_episodes.add(ep_number)
                    season_info.episodes.append(EpisodeInfo(
                        episode_number=ep_number,
                        episode_id=ep.get('Id', ''),
                        episode_name=ep.get('Name', f'Episode {ep_number}'),
                        air_date=ep.get('PremiereDate', ''),
                        has_media=ep.get('HasMedia', True)
                    ))
            
            # 找出缺失的集
            if season_info.expected_episodes > 0:
                # 使用 TMDB 预期集数
                expected_eps = set(expected_episodes_map.get(season_number, []))
                for ep_num in expected_eps:
                    if ep_num not in existing_episodes:
                        season_info.missing_episodes.append(ep_num)
            else:
                # 基于现有集数估算
                if existing_episodes:
                    max_ep = max(existing_episodes)
                    for i in range(1, max_ep + 1):
                        if i not in existing_episodes:
                            season_info.missing_episodes.append(i)
            
            return season_info
            
        except Exception as e:
            logger.error(f"分析季失败 {season.get('Name')}: {e}")
            return None
    
    def get_summary(self, result: DetectionResult) -> str:
        """生成检测摘要"""
        summary = []
        summary.append(f"📺 Emby 缺集检测报告")
        summary.append(f"检测时间：{result.detection_time.strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append(f"使用 TMDB：{'是' if result.use_tmdb else '否'}")
        summary.append(f"剧集总数：{result.total_series}")
        summary.append(f"有缺集的剧集：{result.series_with_missing}")
        summary.append(f"缺失总集数：{result.total_missing_episodes}")
        summary.append(f"耗时：{result.duration_seconds:.2f}秒")
        summary.append("")
        
        # 列出有缺集的剧集
        for series in result.series:
            if series.missing_episodes_count > 0:
                summary.append(f"📌 {series.series_name} ({series.year or '未知年份'})")
                summary.append(f"   状态：{'连载' if series.status == 'ongoing' else '完结'}")
                summary.append(f"   缺失：{series.missing_episodes_count} 集")
                for season in series.seasons:
                    if season.missing_episodes:
                        eps = ', '.join(map(str, season.missing_episodes[:10]))
                        if len(season.missing_episodes) > 10:
                            eps += f"... 等共{len(season.missing_episodes)}集"
                        summary.append(f"   - S{season.season_number:02d}: {eps}")
                summary.append("")
        
        return '\n'.join(summary)
    
    def get_card_data(self, result: DetectionResult) -> List[Dict]:
        """
        转换为卡片流数据格式
        
        Args:
            result: DetectionResult 对象
        
        Returns:
            卡片数据列表
        """
        cards = []
        
        for series in result.series:
            if series.missing_episodes_count > 0:
                card = {
                    'series_id': series.series_id,
                    'series_name': series.series_name,
                    'year': series.year or '未知',
                    'poster': series.poster_url or '',
                    'status': series.status,
                    'tmdb_id': series.tmdb_id,
                    'missing_count': series.missing_episodes_count,
                    'total_seasons': series.total_seasons,
                    'seasons': [
                        {
                            'season_number': s.season_number,
                            'missing_episodes': s.missing_episodes
                        }
                        for s in series.seasons if s.missing_episodes
                    ]
                }
                cards.append(card)
        
        # 按缺集数排序
        cards.sort(key=lambda x: x['missing_count'], reverse=True)
        
        return cards
