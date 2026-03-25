"""
TMDB API 客户端模块
用于获取剧集标准集数信息，对比识别缺集
"""

import httpx
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger


class TMDBClient:
    """TMDB API 客户端"""
    
    def __init__(self, api_key: str, language: str = "zh-CN", proxy_url: Optional[str] = None):
        """
        初始化 TMDB 客户端
        
        Args:
            api_key: TMDB API 密钥
            language: 语言设置，默认中文
            proxy_url: 代理地址
        """
        self.api_key = api_key
        self.language = language
        self.proxy_url = (proxy_url or "").strip()
        self.base_url = "https://api.themoviedb.org/3"
        client_kwargs: Dict[str, Any] = {
            "base_url": self.base_url,
            "headers": {"Content-Type": "application/json"},
            "timeout": 30.0,
        }
        if self.proxy_url:
            client_kwargs["proxies"] = {
                "http://": self.proxy_url,
                "https://": self.proxy_url,
            }
        self.client = httpx.Client(
            **client_kwargs
        )
        logger.info(
            f"TMDB 客户端已初始化 (语言：{language}, 代理：{'启用' if self.proxy_url else '禁用'})"
        )

    def _preferred_auth_modes(self) -> List[str]:
        token = (self.api_key or "").strip()
        if token.count(".") == 2 or token.startswith("eyJ"):
            return ["bearer", "api_key"]
        return ["api_key", "bearer"]

    def _build_request_options(
        self,
        auth_mode: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        request_params = dict(params or {})
        headers: Dict[str, str] = {}

        if auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            request_params["api_key"] = self.api_key

        return request_params, headers

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        operation: str = "TMDB 请求",
    ) -> Tuple[httpx.Response, str]:
        auth_modes = self._preferred_auth_modes()
        response: Optional[httpx.Response] = None

        for index, auth_mode in enumerate(auth_modes):
            request_params, headers = self._build_request_options(auth_mode, params)
            response = self.client.get(path, params=request_params, headers=headers or None)

            if response.status_code in (401, 403) and index < len(auth_modes) - 1:
                logger.warning(
                    f"{operation}鉴权失败，切换鉴权方式重试: "
                    f"status={response.status_code}, auth_mode={auth_mode}"
                )
                continue

            return response, auth_mode

        assert response is not None
        return response, auth_modes[-1]

    @staticmethod
    def _compact_response_text(response: httpx.Response, max_length: int = 200) -> str:
        body = (response.text or "").replace("\n", " ").replace("\r", " ").strip()
        if len(body) > max_length:
            return f"{body[:max_length]}..."
        return body
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            response, auth_mode = self._get("/configuration", operation="TMDB 连接测试")
            logger.info(
                f"TMDB 连接测试响应: status={response.status_code}, auth_mode={auth_mode}"
            )
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
        candidates = self.search_tv_series_candidates(title, year=year, limit=1)
        return candidates[0] if candidates else None

    def search_tv_series_candidates(
        self,
        title: str,
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        搜索多个剧集候选

        Args:
            title: 剧集标题
            year: 年份（可选，用于优先排序）
            limit: 返回数量

        Returns:
            候选结果列表
        """
        try:
            logger.info(
                f"TMDB TV 搜索开始: title={title}, year={year or '-'}, limit={limit}"
            )
            params = {
                "query": title,
                "language": self.language
            }

            response, auth_mode = self._get(
                "/search/tv",
                params=params,
                operation=f"TMDB TV 搜索 {title}",
            )
            if response.status_code == 200:
                results = response.json().get("results", [])
                logger.info(
                    f"TMDB TV 搜索响应: title={title}, status={response.status_code}, "
                    f"auth_mode={auth_mode}, result_count={len(results)}"
                )

                if year and results:
                    target_year = str(year)
                    exact_matches = []
                    other_matches = []
                    for result in results:
                        first_air_date = result.get("first_air_date", "")
                        if first_air_date.startswith(target_year):
                            exact_matches.append(result)
                        else:
                            other_matches.append(result)
                    results = exact_matches + other_matches

                return results[:max(1, limit)]

            logger.warning(
                f"TMDB TV 搜索失败响应: title={title}, status={response.status_code}, "
                f"auth_mode={auth_mode}, body={self._compact_response_text(response)}"
            )
            return []
        except Exception as e:
            logger.error(f"搜索剧集失败 {title}: {e}")
            return []

    def get_tv_feed(self, feed: str, page: int = 1) -> Dict[str, Any]:
        feed_key = (feed or "").strip().lower()
        if feed_key in ("on_the_air", "airing_today", "popular", "top_rated"):
            path = f"/tv/{feed_key}"
        elif feed_key in ("trending_day", "trending_week"):
            window = "day" if feed_key.endswith("_day") else "week"
            path = f"/trending/tv/{window}"
        else:
            raise ValueError(f"Unsupported TMDB feed: {feed}")

        safe_page = max(1, min(int(page or 1), 500))
        params = {"language": self.language, "page": safe_page}

        response, auth_mode = self._get(path, params=params, operation=f"TMDB feed {feed_key}")
        if response.status_code == 200:
            return response.json()

        logger.warning(
            f"TMDB feed 请求失败: feed={feed_key}, status={response.status_code}, auth_mode={auth_mode}, "
            f"body={self._compact_response_text(response)}"
        )
        return {"page": safe_page, "results": [], "total_pages": 0, "total_results": 0}
    
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

            response, _ = self._get(f"/tv/{series_id}", params=params)
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

            response, _ = self._get(f"/tv/{series_id}/season/{season_number}", params=params)
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

            response, _ = self._get(
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

            response, _ = self._get(f"/find/{external_id}", params=params)
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
