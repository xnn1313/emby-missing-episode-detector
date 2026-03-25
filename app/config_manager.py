"""
配置管理模块
支持配置的持久化存储和动态加载
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        env_config_path = os.getenv("CONFIG_PATH")
        self.config_path = Path(config_path or env_config_path or "config/settings.json")
        self._ensure_directory()
        self.config = self._load_config()
        logger.info(f"配置管理器已初始化：{self.config_path}")
    
    def _ensure_directory(self):
        """确保配置目录存在"""
        config_dir = self.config_path.parent
        if config_dir and not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建配置目录：{config_dir}")
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info("配置加载成功")
                return config
            except Exception as e:
                logger.error(f"配置加载失败：{e}")
                return self._get_default_config()
        else:
            logger.warning("配置文件不存在，创建默认配置")
            config = self._get_default_config()
            self._save_config(config)
            return config
    
    def _save_config(self, config: Dict) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info("配置保存成功")
            return True
        except Exception as e:
            logger.error(f"配置保存失败：{e}")
            return False
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "emby": {
                "host": "",
                "api_key": ""
            },
            "libraries": {
                "enabled": False,
                "selected_ids": []
            },
            "tmdb": {
                "enabled": False,
                "api_key": ""
            },
            "detection": {
                "interval_minutes": 60,
                "auto_start": True
            },
            "moviepilot": {
                "host": "",
                "api_key": "",
                "enabled": False,
                "auto_download": True,
                "download_path": ""
            },
            "wecom": {
                "enabled": False,
                "corp_id": "",
                "agent_id": 0,
                "corp_secret": "",
                "token": "",
                "encoding_aes_key": "",
                "base_url": "https://qyapi.weixin.qq.com/cgi-bin"
            },
            "symedia": {
                "enabled": False,
                "host": "",
                "token": "symedia",
                "parent_id": "0"
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点分隔，如 "emby.host"）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键（支持点分隔，如 "emby.host"）
            value: 配置值
            
        Returns:
            是否保存成功
        """
        keys = key.split('.')
        config = self.config
        
        # 导航到倒数第二层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置最后一层
        config[keys[-1]] = value
        
        return self._save_config(self.config)
    
    def get_emby_config(self) -> Dict:
        """获取 Emby 配置"""
        return self.config.get("emby", {})
    
    def set_emby_config(self, host: str, api_key: str) -> bool:
        """设置 Emby 配置"""
        self.config["emby"] = {
            "host": host,
            "api_key": api_key
        }
        return self._save_config(self.config)
    
    def get_library_config(self) -> Dict:
        """获取媒体库配置"""
        return self.config.get("libraries", {})
    
    def set_library_config(self, enabled: bool, selected_ids: List[str]) -> bool:
        """设置媒体库配置"""
        self.config["libraries"] = {
            "enabled": enabled,
            "selected_ids": selected_ids
        }
        return self._save_config(self.config)
    
    def get_tmdb_config(self) -> Dict:
        """获取 TMDB 配置"""
        return self.config.get("tmdb", {})
    
    def set_tmdb_config(self, api_key: str) -> bool:
        """设置 TMDB 配置"""
        self.config["tmdb"] = {
            "enabled": bool(api_key),
            "api_key": api_key
        }
        return self._save_config(self.config)
    
    def get_detection_config(self) -> Dict:
        """获取检测配置"""
        return self.config.get("detection", {})
    
    def set_detection_interval(self, minutes: int) -> bool:
        """设置检测间隔"""
        self.config["detection"]["interval_minutes"] = minutes
        return self._save_config(self.config)
    
    def get_moviepilot_config(self) -> Dict:
        """获取 MoviePilot 配置"""
        return self.config.get("moviepilot", {})
    
    def set_moviepilot_config(self, host: str, username: str = "admin", password: str = "",
                              enabled: bool = True, auto_download: bool = True,
                              download_path: str = "") -> bool:
        """设置 MoviePilot 配置"""
        self.config["moviepilot"] = {
            "host": host,
            "username": username,
            "password": password,
            "enabled": enabled,
            "auto_download": auto_download,
            "download_path": download_path
        }
        return self._save_config(self.config)
    
    def get_hdhive_config(self) -> Dict:
        """获取 HDHive 配置"""
        return self.config.get("hdhive", {
            "enabled": False,
            "api_key": "",
            "base_url": "https://hdhive.com/api/open",
            "proxy": {
                "enabled": False,
                "host": "",
                "port": 0,
                "username": "",
                "password": ""
            },
            "settings": {
                "max_points_per_unlock": 50,
                "prefer_115": True,
                "auto_unlock": False
            }
        })

    def get_symedia_config(self) -> Dict:
        return self.config.get("symedia", {
            "enabled": False,
            "host": "",
            "token": "symedia",
            "parent_id": "0"
        })

    def set_symedia_config(self, host: str, token: str = "symedia", parent_id: str = "0", enabled: bool = True) -> bool:
        self.config["symedia"] = {
            "enabled": bool(enabled),
            "host": host or "",
            "token": token or "symedia",
            "parent_id": str(parent_id or "0")
        }
        return self._save_config(self.config)

    def get_wecom_config(self) -> Dict:
        """获取企业微信配置"""
        return self.config.get("wecom", {
            "enabled": False,
            "corp_id": "",
            "agent_id": 0,
            "corp_secret": "",
            "token": "",
            "encoding_aes_key": "",
            "base_url": "https://qyapi.weixin.qq.com/cgi-bin"
        })
    
    def set_hdhive_config(self, api_key: str = "", base_url: str = "https://hdhive.com/api/open",
                          enabled: bool = False, proxy: Dict = None, settings: Dict = None) -> bool:
        """
        设置 HDHive 配置
        
        Args:
            api_key: API Key
            base_url: API 基础 URL
            enabled: 是否启用
            proxy: 代理配置 {"enabled": bool, "host": str, "port": int, "username": str, "password": str}
            settings: 设置 {"max_points_per_unlock": int, "prefer_115": bool, "auto_unlock": bool}
        """
        self.config["hdhive"] = {
            "enabled": enabled,
            "api_key": api_key,
            "base_url": base_url,
            "proxy": proxy or {
                "enabled": False,
                "host": "",
                "port": 0,
                "username": "",
                "password": ""
            },
            "settings": settings or {
                "max_points_per_unlock": 50,
                "prefer_115": True,
                "auto_unlock": False
            }
        }
        return self._save_config(self.config)

    def set_wecom_config(
        self,
        enabled: bool = False,
        corp_id: str = "",
        agent_id: int = 0,
        corp_secret: str = "",
        token: str = "",
        encoding_aes_key: str = "",
        base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"
    ) -> bool:
        """设置企业微信配置"""
        self.config["wecom"] = {
            "enabled": enabled,
            "corp_id": corp_id,
            "agent_id": agent_id,
            "corp_secret": corp_secret,
            "token": token,
            "encoding_aes_key": encoding_aes_key,
            "base_url": base_url
        }
        return self._save_config(self.config)
    
    def get_all_config(self) -> Dict:
        """获取完整配置"""
        return deepcopy(self.config)
    
    def update_config(self, new_config: Dict) -> bool:
        """批量更新配置"""
        self.config.update(new_config)
        return self._save_config(self.config)


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
