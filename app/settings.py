"""
系统设置模块
实现 Emby/TMDB/代理等配置管理
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from loguru import logger


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "data/config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._ensure_directory()
        self._init_config()
        logger.info(f"配置管理器已初始化：{config_path}")
    
    def _ensure_directory(self):
        """确保目录存在"""
        db_dir = os.path.dirname(self.config_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _init_config(self):
        """初始化配置"""
        if not os.path.exists(self.config_path):
            default_config = {
                "emby": {
                    "host": "http://localhost:8096",
                    "api_key": "",
                    "enabled": True
                },
                "tmdb": {
                    "api_key": "",
                    "language": "zh-CN",
                    "enabled": True
                },
                "telegram": {
                    "bot_token": "",
                    "chat_id": "",
                    "parse_mode": "Markdown",
                    "enabled": False
                },
                "qqbot": {
                    "webhook_url": "",
                    "enabled": False
                },
                "email": {
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "recipient": "",
                    "enabled": False
                },
                "proxy": {
                    "enabled": False,
                    "http": "",
                    "https": ""
                },
                "scan": {
                    "interval_minutes": 60,
                    "notify_on_complete": True,
                    "scan_on_startup": False
                },
                "web": {
                    "host": "0.0.0.0",
                    "port": 8080,
                    "secret_key": ""
                },
                "updated_at": datetime.now().isoformat()
            }
            self._save_config(default_config)
            logger.info("默认配置已创建")
    
    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败：{e}")
            return {}
    
    def _save_config(self, config: Dict):
        """保存配置"""
        config["updated_at"] = datetime.now().isoformat()
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def get_config(self, section: Optional[str] = None) -> Dict:
        """获取配置"""
        config = self._load_config()
        if section:
            return config.get(section, {})
        return config
    
    def update_config(self, section: str, data: Dict) -> bool:
        """
        更新配置
        
        Args:
            section: 配置段落
            data: 新配置数据
        
        Returns:
            是否成功
        """
        config = self._load_config()
        if section not in config:
            config[section] = {}
        
        config[section].update(data)
        self._save_config(config)
        
        logger.info(f"配置已更新：{section}")
        return True
    
    def test_emby_connection(self, host: str, api_key: str) -> Dict:
        """
        测试 Emby 连接
        
        Args:
            host: Emby 主机地址
            api_key: API 密钥
        
        Returns:
            测试结果
        """
        try:
            import httpx
            response = httpx.get(
                f"{host}/System/Info",
                headers={"X-Emby-Token": api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": "连接成功",
                    "server_name": data.get("ServerName", "Unknown"),
                    "version": data.get("Version", "Unknown")
                }
            else:
                return {
                    "success": False,
                    "message": f"连接失败：HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接异常：{str(e)}"
            }
    
    def test_tmdb_connection(self, api_key: str) -> Dict:
        """
        测试 TMDB 连接
        
        Args:
            api_key: TMDB API 密钥
        
        Returns:
            测试结果
        """
        try:
            import httpx
            response = httpx.get(
                "https://api.themoviedb.org/3/configuration",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "连接成功"
                }
            else:
                return {
                    "success": False,
                    "message": f"连接失败：HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接异常：{str(e)}"
            }
    
    def test_telegram_connection(self, bot_token: str, chat_id: str) -> Dict:
        """
        测试 Telegram 连接
        
        Args:
            bot_token: Bot Token
            chat_id: 聊天 ID
        
        Returns:
            测试结果
        """
        try:
            import httpx
            response = httpx.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    # 发送测试消息
                    test_msg = httpx.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": "🧪 这是一条测试消息，Telegram 通知功能正常！"
                        },
                        timeout=10
                    )
                    
                    if test_msg.status_code == 200:
                        return {
                            "success": True,
                            "message": "连接成功，测试消息已发送",
                            "bot_name": data["result"].get("username", "Unknown")
                        }
                
                return {
                    "success": False,
                    "message": "Bot 验证失败"
                }
            else:
                return {
                    "success": False,
                    "message": f"连接失败：HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接异常：{str(e)}"
            }
    
    def get_all_settings(self) -> Dict:
        """获取所有设置项"""
        return {
            "emby": {
                "fields": [
                    {"key": "host", "label": "Emby 服务器地址", "type": "url", "required": True},
                    {"key": "api_key", "label": "API 密钥", "type": "password", "required": True},
                    {"key": "enabled", "label": "启用", "type": "boolean"}
                ]
            },
            "tmdb": {
                "fields": [
                    {"key": "api_key", "label": "TMDB API 密钥", "type": "password", "required": False},
                    {"key": "language", "label": "语言", "type": "select", "options": ["zh-CN", "en-US", "ja-JP"]},
                    {"key": "enabled", "label": "启用", "type": "boolean"}
                ]
            },
            "telegram": {
                "fields": [
                    {"key": "bot_token", "label": "Bot Token", "type": "password"},
                    {"key": "chat_id", "label": "聊天 ID", "type": "text"},
                    {"key": "enabled", "label": "启用", "type": "boolean"}
                ]
            },
            "proxy": {
                "fields": [
                    {"key": "enabled", "label": "启用代理", "type": "boolean"},
                    {"key": "http", "label": "HTTP 代理", "type": "text"},
                    {"key": "https", "label": "HTTPS 代理", "type": "text"}
                ]
            },
            "scan": {
                "fields": [
                    {"key": "interval_minutes", "label": "扫描间隔 (分钟)", "type": "number"},
                    {"key": "notify_on_complete", "label": "完成后通知", "type": "boolean"},
                    {"key": "scan_on_startup", "label": "启动时扫描", "type": "boolean"}
                ]
            }
        }


# 全局配置管理器实例
config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global config_manager
    if config_manager is None:
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        config_path = project_root / "data" / "config.json"
        config_manager = ConfigManager(str(config_path))
    return config_manager
