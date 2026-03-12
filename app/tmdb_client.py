"""
TMDB API 客户端模块
用于获取剧集标准集数信息，对比识别缺集
"""

import httpx
from typing import Optional, List, Dict, Any
from loguru import logger


class TMDBClient:
    """TMDB API 客户端"""
    
    def __init__(self, api_key: str, language: str = "zh-CN"):
        """
        初始化 TMDB 客户端
        
        Args:
            api_key: TMDB API 密钥
            language: 语言设置，默认中文
        """
        self.api_key = api_key
        self.language = language
        self.base_url = "https://api.themoviedb.org/3"
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        logger.info(f"TMDB 客户端已初始化 (语言：{language})")
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            response = self.client.get("/configuration")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"TMDB 连接测试失败：{e}")
            return False
    
    def search_tv_series(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        搜索剧集
        
        Args:
            title: 剧集标题
            year: 年份（可选，用于精确匹配）
        
        Returns:
            匹配的剧集信息，无匹配则返回 None
        """
        try:
            params = {
                "query": title,
                "language": self.language
            }
            
            response = self.client.get("/search/tv", params=params)
            if response.status_code == 200:
                results = response.json().get("results", [])
                
                # 如果有年份，精确匹配
                if year and results:
                    for result in results:
                        first_air_date = result.get("first_air_date", "")
                        if first_air_date.startswith(str(year)):
                            return result
                    # 如果没有精确匹配，返回第一个结果
                    return results[0] if results else None
                
                return results[0] if results else None
            
            return None
        except Exception as e:
            logger.error(f"搜索剧集失败 {title}: {e}")
            return None
    
    def get_tv_series_details(self, series_id: int) -> Optional[Dict]:
        """
        获取剧集详情
        
        Args:
            series_id: TMDB 剧集 ID
        
        Returns:
            剧集详细信息
        """
        try:
            params = {
                "language": self.language,
                "external_source": "tvdb_id"
            }
            
            response = self.client.get(f"/tv/{series_id}", params=params)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"获取剧集详情失败 {series_id}: {e}")
            return None
    
    def get_season_details(self, series_id: int, season_number: int) -> Optional[Dict]:
        """
        获取季详情
        
        Args:
            series_id: TMDB 剧集 ID
            season_number: 季号（0 为特别篇）
        
        Returns:
            季详细信息，包含所有集
        """
        try:
            params = {
                "language": self.language,
                "append_to_response": "external_ids"
            }
            
            response = self.client.get(f"/tv/{series_id}/season/{season_number}", params=params)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"获取季详情失败 S{season_number}: {e}")
            return None
    
    def get_episode_details(self, series_id: int, season_number: int, episode_number: int) -> Optional[Dict]:
        """
        获取单集详情
        
        Args:
            series_id: TMDB 剧集 ID
            season_number: 季号
            episode_number: 集号
        
        Returns:
            单集详细信息
        """
        try:
            params = {"language": self.language}
            
            response = self.client.get(
                f"/tv/{series_id}/season/{season_number}/episode/{episode_number}",
                params=params
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"获取集详情失败 S{season_number}E{episode_number}: {e}")
            return None
    
    def find_by_external_id(
        self,
        source: str,
        external_id: str
    ) -> Optional[Dict]:
        """
        通过外部 ID 查找剧集
        
        Args:
            source: 来源 (tvdb, imdb, tmdb)
            external_id: 外部 ID
        
        Returns:
            查找结果
        """
        try:
            params = {
                "external_source": f"{source}_id",
                "language": self.language
            }
            
            response = self.client.get(f"/find/{external_id}", params=params)
            if response.status_code == 200:
                data = response.json()
                tv_results = data.get("tv_results", [])
                return tv_results[0] if tv_results else None
            return None
        except Exception as e:
            logger.error(f"通过外部 ID 查找失败 {source}:{external_id}: {e}")
            return None
    
    def get_expected_episodes(
        self,
        series_id: int,
        season_number: int
    ) -> int:
        """
        获取某季应该有的集数
        
        Args:
            series_id: TMDB 剧集 ID
            season_number: 季号
        
        Returns:
            预期集数，获取失败返回 0
        """
        season = self.get_season_details(series_id, season_number)
        if season:
            return len(season.get("episodes", []))
        return 0
    
    def get_all_seasons_episodes(
        self,
        series_id: int
    ) -> Dict[int, List[int]]:
        """
        获取所有季的集数信息
        
        Args:
            series_id: TMDB 剧集 ID
        
        Returns:
            {季号：[集号列表]}
        """
        result = {}
        
        series = self.get_tv_series_details(series_id)
        if not series:
            return result
        
        for season in series.get("seasons", []):
            season_number = season.get("season_number", 0)
            
            # 跳过没有集数的季
            if season.get("episode_count", 0) == 0:
                continue
            
            season_details = self.get_season_details(series_id, season_number)
            if season_details:
                episodes = season_details.get("episodes", [])
                result[season_number] = [ep.get("episode_number", i+1) for i, ep in enumerate(episodes)]
        
        return result
    
    def close(self):
        """关闭客户端"""
        self.client.close()


class TMDBMatcher:
    """TMDB 匹配器 - 用于 Emby 剧集与 TMDB 的匹配"""
    
    def __init__(self, tmdb_client: TMDBClient):
        self.tmdb = tmdb_client
        self.cache = {}  # 简单的内存缓存
        logger.info("TMDB 匹配器已初始化")
    
    def match_series(
        self,
        emby_series: Dict
    ) -> Optional[int]:
        """
        匹配 Emby 剧集到 TMDB
        
        Args:
            emby_series: Emby 剧集信息
        
        Returns:
            TMDB ID，匹配失败返回 None
        """
        series_id = emby_series.get("Id")
        
        # 检查缓存
        if series_id in self.cache:
            return self.cache[series_id]
        
        # 尝试从 ProviderIds 获取
        provider_ids = emby_series.get("ProviderIds", {})
        
        # 优先使用 TVDB ID
        if "Tvdb" in provider_ids:
            result = self.tmdb.find_by_external_id("tvdb", provider_ids["Tvdb"])
            if result:
                tmdb_id = result.get("id")
                self.cache[series_id] = tmdb_id
                return tmdb_id
        
        # 使用 IMDb ID
        if "Imdb" in provider_ids:
            result = self.tmdb.find_by_external_id("imdb", provider_ids["Imdb"])
            if result:
                tmdb_id = result.get("id")
                self.cache[series_id] = tmdb_id
                return tmdb_id
        
        # 最后尝试标题搜索
        title = emby_series.get("Name", "")
        year = None
        
        # 从 PremiereDate 提取年份
        premiere_date = emby_series.get("PremiereDate", "")
        if premiere_date:
            try:
                year = int(premiere_date[:4])
            except:
                pass
        
        result = self.tmdb.search_tv_series(title, year)
        if result:
            tmdb_id = result.get("id")
            self.cache[series_id] = tmdb_id
            return tmdb_id
        
        logger.warning(f"无法匹配剧集到 TMDB: {title}")
        return None
    
    def get_expected_episodes_for_season(
        self,
        emby_series: Dict,
        season_number: int
    ) -> List[int]:
        """
        获取某季预期的集号列表
        
        Args:
            emby_series: Emby 剧集信息
            season_number: 季号
        
        Returns:
            预期集号列表
        """
        tmdb_id = self.match_series(emby_series)
        if not tmdb_id:
            return []
        
        season = self.tmdb.get_season_details(tmdb_id, season_number)
        if not season:
            return []
        
        return [ep.get("episode_number", i+1) for i, ep in enumerate(season.get("episodes", []))]
    
    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        logger.info("TMDB 匹配缓存已清除")
