"""
MoviePilot API 客户端模块
支持搜索、下载、进度查询等功能
"""

import httpx
from typing import Optional, List, Dict, Any
from loguru import logger


class MoviePilotClient:
    """MoviePilot API 客户端"""
    
    def __init__(self, host: str, username: str = "admin", password: str = ""):
        """
        初始化 MoviePilot 客户端
        
        Args:
            host: MoviePilot 服务器地址 (如 http://localhost:3000)
            username: MoviePilot 用户名
            password: MoviePilot 密码
        """
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.token = self._get_token()
        
        self.client = httpx.Client(
            base_url=self.host,
            headers={
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            },
            timeout=30.0
        )
        logger.info(f"MoviePilot 客户端已初始化：{self.host}")
        logger.info(f"用户：{username}, Token 获取：{'成功' if self.token else '失败'}")
    
    def _get_token(self) -> str:
        """通过登录接口获取 Bearer Token"""
        try:
            import urllib.parse
            data = {
                'username': self.username,
                'password': self.password
            }
            response = httpx.post(
                f'{self.host}/api/v1/login/access-token',
                data=urllib.parse.urlencode(data),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10.0
            )
            if response.status_code == 200:
                result = response.json()
                token = result.get('access_token', '')
                logger.info(f"MoviePilot 登录成功，Token 已获取")
                return token
            else:
                logger.error(f"MoviePilot 登录失败：{response.status_code} - {response.text}")
                return ''
        except Exception as e:
            logger.error(f"MoviePilot 登录异常：{e}")
            return ''
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            response = self.client.get('/api/v1/system/status')
            return response.status_code == 200
        except Exception as e:
            logger.error(f"连接测试失败：{e}")
            return False
    
    def subscribe_tv(self, title: str, year: Optional[int] = None, 
                     season: Optional[int] = None, fuzzy_match: bool = True) -> Dict:
        """
        订阅剧集（推荐方式，自动搜索下载）
        MoviePilot API: POST /api/v1/subscribe/
        """
        try:
            data = {
                'name': title,
                'type': '电视剧',
                'season': season if season else 1,
            }
            
            if year:
                data['year'] = str(year)
            
            logger.info(f"正在订阅：{title} S{season or '*'} @ {self.host}")
            logger.info(f"💡 MoviePilot 会自动识别已存在的集数，只下载缺失的集数")
            logger.info(f"订阅数据：{data}")
            
            response = self.client.post('/api/v1/subscribe/', json=data)
            logger.info(f"订阅响应状态码：{response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"订阅成功：{title} S{season}")
                return result
            else:
                logger.error(f"订阅失败：{response.status_code} - {response.text}")
            return {}
        except Exception as e:
            logger.error(f"订阅异常 {title}: {e}")
            return {}
    
    def close(self):
        """关闭客户端"""
        self.client.close()
