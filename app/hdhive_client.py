"""
HDHive Open API 客户端模块
用于查询和解锁 HDHive 资源
"""

import httpx
from typing import Optional, List, Dict, Any
from loguru import logger
from dataclasses import dataclass


@dataclass
class HDHiveConfig:
    """HDHive 配置"""
    api_key: str = ""
    base_url: str = "https://hdhive.com/api/open"
    enabled: bool = False
    # 代理配置
    proxy_enabled: bool = False
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_username: str = ""
    proxy_password: str = ""
    # 设置
    max_points_per_unlock: int = 50
    prefer_115: bool = True
    auto_unlock: bool = False


class HDHiveError(Exception):
    """HDHive API 错误"""
    def __init__(self, code: str, message: str, description: str = ""):
        self.code = code
        self.message = message
        self.description = description
        super().__init__(f"[{code}] {message}: {description}")


class HDHiveClient:
    """HDHive Open API 客户端"""
    
    # 错误码映射
    ERROR_CODES = {
        "MISSING_API_KEY": "缺少 API Key",
        "INVALID_API_KEY": "API Key 无效",
        "DISABLED_API_KEY": "API Key 已被禁用",
        "EXPIRED_API_KEY": "API Key 已过期",
        "VIP_REQUIRED": "需要 Premium 会员",
        "INSUFFICIENT_POINTS": "积分不足",
        "ENDPOINT_QUOTA_EXCEEDED": "API 配额已用尽",
        "RATE_LIMIT_EXCEEDED": "请求频率过高",
    }
    
    def __init__(self, config: HDHiveConfig):
        """
        初始化 HDHive 客户端
        
        Args:
            config: HDHive 配置
        """
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        
        # 构建请求头
        self.headers = {
            "X-API-Key": config.api_key,
            "Content-Type": "application/json"
        }
        
        # 构建代理配置
        self.proxies = None
        if config.proxy_enabled and config.proxy_host:
            proxy_url = f"http://{config.proxy_host}:{config.proxy_port}"
            if config.proxy_username and config.proxy_password:
                proxy_url = f"http://{config.proxy_username}:{config.proxy_password}@{config.proxy_host}:{config.proxy_port}"
            self.proxies = {
                "http://": proxy_url,
                "https://": proxy_url
            }
        
        # 创建 HTTP 客户端
        self.client = httpx.Client(
            headers=self.headers,
            proxies=self.proxies,
            timeout=httpx.Timeout(timeout=30.0, connect=10.0, read=30.0, write=30.0)
        )
        
        logger.info(f"HDHive 客户端已初始化：{self.base_url}")
    
    def close(self):
        """关闭客户端"""
        if self.client:
            self.client.close()
    
    def _handle_error(self, response: httpx.Response, data: dict):
        """处理 API 错误"""
        code = data.get("code", str(response.status_code))
        message = data.get("message", "未知错误")
        description = data.get("description", "")
        
        # 中文错误描述
        cn_message = self.ERROR_CODES.get(code, message)
        
        raise HDHiveError(code, cn_message, description)
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """
        发送请求
        
        Args:
            method: HTTP 方法
            path: API 路径
            **kwargs: 其他请求参数
            
        Returns:
            响应数据
        """
        url = f"{self.base_url}{path}"
        
        try:
            response = self.client.request(method, url, **kwargs)
            data = response.json()
            
            # 检查响应状态
            if not data.get("success", False):
                self._handle_error(response, data)
            
            logger.debug(f"HDHive API {method} {path}: {response.status_code}")
            return data
            
        except httpx.TimeoutException:
            raise HDHiveError("TIMEOUT", "请求超时", "API 请求超时，请稍后重试")
        except httpx.RequestError as e:
            raise HDHiveError("NETWORK_ERROR", "网络错误", str(e))
    
    # ==================== 通用接口 ====================
    
    def ping(self) -> Dict[str, Any]:
        """
        健康检查，验证 API Key 是否有效
        
        Returns:
            {
                "message": "pong",
                "api_key_id": 1,
                "name": "My App"
            }
        """
        data = self._request("GET", "/ping")
        return data.get("data", {})
    
    def get_quota(self) -> Dict[str, Any]:
        """
        获取 API 配额信息
        
        Returns:
            {
                "daily_reset": 1707494400,
                "endpoint_limit": 1000,
                "endpoint_remaining": 850
            }
        """
        data = self._request("GET", "/quota")
        return data.get("data", {})
    
    # ==================== 资源接口 ====================
    
    def get_resources(self, tmdb_id: str, media_type: str = "tv") -> List[Dict[str, Any]]:
        """
        根据 TMDB ID 获取资源列表
        
        Args:
            tmdb_id: TMDB ID
            media_type: 媒体类型 "movie" 或 "tv"
            
        Returns:
            资源列表
        """
        if media_type not in ("movie", "tv"):
            raise HDHiveError("400", "参数错误", "media_type 必须是 movie 或 tv")
        
        try:
            data = self._request("GET", f"/resources/{media_type}/{tmdb_id}")
            resources = data.get("data", [])
            logger.info(f"HDHive 获取资源：TMDB {tmdb_id} ({media_type}) -> {len(resources)} 个资源")
            return resources
        except Exception as e:
            logger.error(f"HDHive 获取资源失败：TMDB {tmdb_id}, 错误：{e}")
            return []
    
    def unlock_resource(self, slug: str) -> Dict[str, Any]:
        """
        解锁资源，获取下载链接
        
        Args:
            slug: 资源唯一标识
            
        Returns:
            {
                "url": "https://pan.example.com/s/abc123",
                "access_code": "x1y2",
                "full_url": "https://pan.example.com/s/abc123?pwd=x1y2",
                "already_owned": false
            }
        """
        data = self._request("POST", "/resources/unlock", json={"slug": slug})
        return data.get("data", {})
    
    def check_resource(self, url: str) -> Dict[str, Any]:
        """
        检查资源链接的网盘类型
        
        Args:
            url: 资源分享链接
            
        Returns:
            {
                "website": "115",
                "url": "https://115.com/s/abc123",
                "base_link": "https://115.com/s/abc123",
                "access_code": "1234",
                "default_unlock_points": 10
            }
        """
        data = self._request("POST", "/check/resource", json={"url": url})
        return data.get("data", {})
    
    # ==================== 用户接口（需要 Premium）====================
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        获取当前用户信息（需要 Premium）
        
        Returns:
            用户信息，包含积分余额等
        """
        data = self._request("GET", "/me")
        return data.get("data", {})
    
    def checkin(self, is_gambler: bool = False) -> Dict[str, Any]:
        """
        每日签到（需要 Premium）
        
        Args:
            is_gambler: 是否使用赌狗模式
            
        Returns:
            签到结果
        """
        data = self._request("POST", "/checkin", json={"is_gambler": is_gambler})
        return data.get("data", {})
    
    # ==================== 业务方法 ====================
    
    def search_tv_resources(self, tmdb_id: str, season: int = None, 
                            prefer_115: bool = True) -> List[Dict[str, Any]]:
        """
        搜索电视剧资源并筛选（通过 TMDB ID）
        
        Args:
            tmdb_id: TMDB ID
            season: 季号（可选筛选）
            prefer_115: 是否优先 115 网盘
            
        Returns:
            筛选后的资源列表
        """
        logger.info(f"HDHive 搜索 TV 资源：TMDB ID={tmdb_id}, season={season}, prefer_115={prefer_115}")
        resources = self.get_resources(tmdb_id, "tv")
        logger.info(f"HDHive 原始资源数：{len(resources)}")
        
        # 筛选 115 网盘
        if prefer_115 and resources:
            resources_115 = [r for r in resources if self._is_115_resource(r)]
            logger.info(f"HDHive 115 资源数：{len(resources_115)}")
            if resources_115:
                resources = resources_115
        
        # 按积分排序（免费优先）
        resources.sort(key=lambda r: r.get("unlock_points") or 0)
        
        return resources
    
    def _is_115_resource(self, resource: Dict[str, Any]) -> bool:
        """检查是否为 115 网盘资源"""
        # 可以通过资源的某些字段判断
        # HDHive 返回的资源可能包含 pan_type 字段
        return resource.get("pan_type") == "115" or "115" in str(resource.get("title", "")).lower()
    
    def get_user_points(self) -> int:
        """
        获取用户当前积分
        
        Returns:
            积分余额
        """
        try:
            user_info = self.get_user_info()
            return user_info.get("user_meta", {}).get("points", 0)
        except HDHiveError:
            return 0
    
    def can_unlock(self, points_needed: int) -> bool:
        """
        检查是否有足够积分解锁
        
        Args:
            points_needed: 所需积分
            
        Returns:
            是否可以解锁
        """
        current_points = self.get_user_points()
        return current_points >= points_needed


# 便捷函数
def create_client_from_config(config_dict: Dict[str, Any]) -> HDHiveClient:
    """
    从配置字典创建客户端
    
    Args:
        config_dict: 配置字典
        
    Returns:
        HDHive 客户端实例
    """
    config = HDHiveConfig(
        api_key=config_dict.get("api_key", ""),
        base_url=config_dict.get("base_url", "https://hdhive.com/api/open"),
        enabled=config_dict.get("enabled", False),
        proxy_enabled=config_dict.get("proxy", {}).get("enabled", False),
        proxy_host=config_dict.get("proxy", {}).get("host", ""),
        proxy_port=config_dict.get("proxy", {}).get("port", 0),
        proxy_username=config_dict.get("proxy", {}).get("username", ""),
        proxy_password=config_dict.get("proxy", {}).get("password", ""),
        max_points_per_unlock=config_dict.get("settings", {}).get("max_points_per_unlock", 50),
        prefer_115=config_dict.get("settings", {}).get("prefer_115", True),
        auto_unlock=config_dict.get("settings", {}).get("auto_unlock", False),
    )
    return HDHiveClient(config)