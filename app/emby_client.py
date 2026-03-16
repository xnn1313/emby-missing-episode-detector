"""
Emby API 客户端模块
参考 MoviePilot 的 API 设计风格
"""

import httpx
from typing import Optional, List, Dict, Any
from loguru import logger


class EmbyClient:
    """Emby API 客户端"""
    
    def __init__(self, host: str, api_key: str):
        """
        初始化 Emby 客户端
        
        Args:
            host: Emby 服务器地址 (如 http://localhost:8096)
            api_key: API 密钥
        """
        # 标准化 host（确保有 scheme）
        if not host.startswith(('http://', 'https://')):
            host = 'http://' + host
        
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.client = httpx.Client(
            base_url=self.host,
            headers={
                'X-Emby-Token': api_key,
                'Content-Type': 'application/json'
            },
            timeout=httpx.Timeout(timeout=30.0, connect=5.0, read=30.0, write=30.0)
        )
        logger.info(f"Emby 客户端已初始化：{self.host}")
    
    def close(self):
        """关闭客户端（释放连接池）"""
        if self.client:
            self.client.close()
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            response = self.client.get('/System/Info')
            return response.status_code == 200
        except Exception as e:
            logger.error(f"连接测试失败：{e}")
            return False
    
    def get_system_info(self) -> Optional[Dict]:
        """获取系统信息"""
        try:
            response = self.client.get('/System/Info')
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"获取系统信息失败：{e}")
            return None
    
    def get_media_libraries(self) -> List[Dict]:
        """获取媒体库列表"""
        try:
            response = self.client.get('/Library/VirtualFolders')
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"获取媒体库失败：{e}")
            return []
    
    def get_tv_shows(self, library_id: Optional[str] = None, library_ids: Optional[List[str]] = None, dedup_by_name: bool = True, limit: int = 10000) -> List[Dict]:
        """
        获取所有剧集
        
        Args:
            library_id: 单个媒体库 ID（已废弃，兼容用）
            library_ids: 媒体库 ID 列表，None 时获取所有库的剧集
            dedup_by_name: 是否按名称 + 年份去重（解决 Emby 重复刮削问题）
        
        Returns:
            剧集列表
        """
        items = []
        
        # 兼容旧参数
        if library_id and not library_ids:
            library_ids = [library_id]
        
        try:
            # 如果指定了媒体库，遍历每个库获取剧集
            if library_ids:
                all_items = []
                for lib_id in library_ids:
                    params = {
                        'IncludeItemTypes': 'Series',
                        'Recursive': True,
                        'ParentId': lib_id,
                        'Fields': 'Overview,AirTime,Studios,Genres,ProductionYear,PremiereDate'
                    }
                    response = self.client.get('/Items', params=params)
                    if response.status_code == 200:
                        data = response.json()
                        all_items.extend(data.get('Items', []))
                
                items = self._deduplicate_items(all_items, dedup_by_name)
                logger.info(f"从 {len(library_ids)} 个媒体库获取到 {len(items)} 个剧集（去重后）")
            else:
                # 获取所有库的剧集（带分页和 limit）
                params = {
                    'IncludeItemTypes': 'Series',
                    'Recursive': True,
                    'Fields': 'Overview,AirTime,Studios,Genres,ProductionYear,PremiereDate',
                    'Limit': limit
                }
                response = self.client.get('/Items', params=params)
                if response.status_code == 200:
                    data = response.json()
                    all_items = data.get('Items', [])
                    total_count = data.get('TotalRecordCount', len(all_items))
                    
                    # 如果数据量超过 limit，记录警告
                    if total_count > limit:
                        logger.warning(f"剧集数量 ({total_count}) 超过 limit ({limit})，可能漏数据。建议增加 limit 或实现分页")
                    
                    items = self._deduplicate_items(all_items, dedup_by_name)
                    logger.info(f"获取到 {len(items)} 个剧集（去重后），总数约：{total_count}")
        except Exception as e:
            logger.error(f"获取剧集失败：{e}")
        
        return items
    
    def _deduplicate_items(self, items: List[Dict], by_name: bool = True) -> List[Dict]:
        """
        去重剧集列表
        
        Args:
            items: 剧集列表
            by_name: True=按名称 + 年份去重，False=按 ID 去重
        
        Returns:
            去重后的剧集列表
        """
        if not by_name:
            # 按 ID 去重
            seen_ids = set()
            unique_items = []
            for item in items:
                item_id = item.get('Id')
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
            return unique_items
        
        # 按名称 + 年份去重（保留 ID 最小的，通常是最早创建的）
        seen_keys = {}
        for item in items:
            name = item.get('Name', 'Unknown')
            year = item.get('ProductionYear') or item.get('PremiereDate', '')[:4] if item.get('PremiereDate') else ''
            key = f"{name}__{year}"
            
            if key not in seen_keys:
                seen_keys[key] = item
            else:
                # 保留 ID 较小的（通常是最早刮削的）
                existing_id = int(seen_keys[key].get('Id', 0))
                current_id = int(item.get('Id', 0))
                if current_id < existing_id:
                    seen_keys[key] = item
        
        logger.info(f"去重：{len(items)} → {len(seen_keys)} 个剧集")
        return list(seen_keys.values())
    
    def get_seasons(self, series_id: str) -> List[Dict]:
        """
        获取剧集的所有季（自动去重）
        
        Args:
            series_id: 剧集 ID
        
        Returns:
            去重后的季列表
        """
        try:
            response = self.client.get(f'/Shows/{series_id}/Seasons')
            response.raise_for_status()  # 对非 2xx 响应抛出异常
            items = response.json().get('Items', [])
            # 去重：按 season_id + season_number 组合去重
            seen = {}
            for item in items:
                season_id = item.get('Id')
                season_num = item.get('IndexNumber', 0)
                key = f"{season_id}__{season_num}"
                if key not in seen:
                    seen[key] = item
            logger.debug(f"季去重：{len(items)} → {len(seen)} (series_id={series_id})")
            return list(seen.values())
        except httpx.HTTPStatusError as e:
            logger.warning(f"获取季信息失败 {series_id}: HTTP {e.response.status_code}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"获取季信息失败 {series_id}: {e}", exc_info=True)
            return []
    
    def get_episodes_batch(self, series_ids: List[str]) -> Dict[str, List[Dict]]:
        """
        批量获取多个剧集的所有集（优化性能）
        注意：Emby API 不支持直接按 SeriesId 列表过滤，需要分批次获取
        
        Args:
            series_ids: 剧集 ID 列表
        
        Returns:
            {series_id: [episodes]}
        """
        all_episodes = {}
        
        try:
            # 方案：先获取所有 Episode，然后在内存中过滤
            # 使用分页避免单次请求数据过大
            page_size = 5000
            start_index = 0
            total_fetched = 0
            
            while True:
                params = {
                    'IncludeItemTypes': 'Episode',
                    'Recursive': True,
                    'Fields': 'IndexNumber,ParentIndexNumber,SeriesId,Name,PremiereDate',
                    'IsMissing': 'False',
                    'StartIndex': start_index,
                    'Limit': page_size
                }
                response = self.client.get('/Items', params=params)
                if response.status_code != 200:
                    logger.warning(f"分页获取集失败：{response.status_code}")
                    break
                    
                data = response.json()
                episodes = data.get('Items', [])
                total_items = data.get('TotalRecordCount', 0)
                
                if not episodes:
                    break
                
                # 按剧集 ID 分组
                for ep in episodes:
                    series_id = ep.get('SeriesId')
                    if series_id and series_id in series_ids:
                        if series_id not in all_episodes:
                            all_episodes[series_id] = []
                        all_episodes[series_id].append(ep)
                
                total_fetched += len(episodes)
                start_index += page_size
                
                logger.debug(f"已获取 {total_fetched}/{total_items} 集，{len(all_episodes)} 个剧集有数据")
                
                # 如果已经获取完所有数据
                if start_index >= total_items:
                    break
            
            logger.info(f"批量获取完成：{total_fetched} 集，{len(all_episodes)}/{len(series_ids)} 个剧集有数据")
            
        except Exception as e:
            logger.error(f"批量获取集信息失败：{e}")
        
        return all_episodes
    
    def get_episodes(self, series_id: str, season_id: str) -> List[Dict]:
        """
        获取某一季的所有集（兼容旧方法）
        
        Args:
            series_id: 剧集 ID
            season_id: 季 ID
        """
        try:
            params = {'SeasonId': season_id}
            response = self.client.get(f'/Shows/{series_id}/Episodes', params=params)
            if response.status_code == 200:
                return response.json().get('Items', [])
            return []
        except Exception as e:
            logger.error(f"获取集信息失败 {season_id}: {e}")
            return []
    
    def get_item(self, item_id: str) -> Optional[Dict]:
        """获取单个项目详情"""
        try:
            response = self.client.get(f'/Users/me/Items/{item_id}')
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"获取项目详情失败 {item_id}: {e}")
            return None
    
    def get_tmdb_id(self, item_id: str) -> Optional[str]:
        """
        获取剧集的 TMDB ID
        
        Args:
            item_id: Emby 项目 ID
            
        Returns:
            TMDB ID 或 None
        """
        try:
            item = self.get_item(item_id)
            if not item:
                return None
            
            # 从 ProviderIds 字段获取
            provider_ids = item.get('ProviderIds', {})
            tmdb_id = provider_ids.get('Tmdb') or provider_ids.get('TMDB')
            
            if tmdb_id:
                logger.debug(f"获取 TMDB ID: {item_id} -> {tmdb_id}")
                return tmdb_id
            
            # 尝试从 ExternalUrls 获取
            external_urls = item.get('ExternalUrls', [])
            for url in external_urls:
                if 'themoviedb' in url.get('Url', '').lower():
                    # 从 URL 中提取 ID
                    url_parts = url.get('Url', '').split('/')
                    for part in reversed(url_parts):
                        if part.isdigit():
                            logger.debug(f"从 ExternalUrls 获取 TMDB ID: {item_id} -> {part}")
                            return part
            
            logger.warning(f"未找到 TMDB ID: {item_id}")
            return None
            
        except Exception as e:
            logger.error(f"获取 TMDB ID 失败 {item_id}: {e}")
            return None
    
    def close(self):
        """关闭客户端"""
        self.client.close()
