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
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.client = httpx.Client(
            base_url=self.host,
            headers={
                'X-Emby-Token': api_key,
                'Content-Type': 'application/json'
            },
            timeout=30.0
        )
        logger.info(f"Emby 客户端已初始化：{self.host}")
    
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
    
    def get_tv_shows(self, library_id: Optional[str] = None, library_ids: Optional[List[str]] = None, dedup_by_name: bool = True) -> List[Dict]:
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
                # 获取所有库的剧集
                params = {
                    'IncludeItemTypes': 'Series',
                    'Recursive': True,
                    'Fields': 'Overview,AirTime,Studios,Genres,ProductionYear,PremiereDate'
                }
                response = self.client.get('/Items', params=params)
                if response.status_code == 200:
                    data = response.json()
                    all_items = data.get('Items', [])
                    items = self._deduplicate_items(all_items, dedup_by_name)
                    logger.info(f"获取到 {len(items)} 个剧集（去重后）")
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
        获取剧集的所有季
        
        Args:
            series_id: 剧集 ID
        """
        try:
            response = self.client.get(f'/Shows/{series_id}/Seasons')
            if response.status_code == 200:
                return response.json().get('Items', [])
            return []
        except Exception as e:
            logger.error(f"获取季信息失败 {series_id}: {e}")
            return []
    
    def get_episodes(self, series_id: str, season_id: str) -> List[Dict]:
        """
        获取某一季的所有集
        
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
    
    def close(self):
        """关闭客户端"""
        self.client.close()
