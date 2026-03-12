"""
Telegram Bot 通知模块
实现即时推送缺集检测报告
"""

import httpx
from typing import Optional, List, Dict
from loguru import logger
from app.notifier import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """Telegram Bot 通知器"""
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        parse_mode: str = "Markdown"
    ):
        """
        初始化 Telegram 通知器
        
        Args:
            bot_token: Bot Token (从 @BotFather 获取)
            chat_id: 接收消息的聊天 ID
            parse_mode: 消息解析模式 (Markdown/HTML)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        logger.info(f"Telegram 通知器已初始化 (Chat ID: {chat_id})")
    
    def send(
        self,
        title: str,
        content: str,
        disable_notification: bool = False
    ) -> bool:
        """
        发送文本消息
        
        Args:
            title: 消息标题
            content: 消息内容
            disable_notification: 是否静默发送
        
        Returns:
            发送是否成功
        """
        try:
            text = f"*{title}*\n\n{content}"
            
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": True
            }
            
            if disable_notification:
                payload["disable_notification"] = True
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/sendMessage",
                    json=payload
                )
            
            if response.status_code == 200:
                logger.info("Telegram 消息发送成功")
                return True
            else:
                logger.error(f"Telegram 消息发送失败：{response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram 消息发送异常：{e}")
            return False
    
    def send_with_photo(
        self,
        title: str,
        content: str,
        photo_url: str,
        disable_notification: bool = False
    ) -> bool:
        """
        发送带图片的消息
        
        Args:
            title: 消息标题
            content: 消息内容
            photo_url: 图片 URL
            disable_notification: 是否静默发送
        
        Returns:
            发送是否成功
        """
        try:
            caption = f"*{title}*\n\n{content}"
            
            payload = {
                "chat_id": self.chat_id,
                "caption": caption,
                "parse_mode": self.parse_mode
            }
            
            files = {"photo": photo_url}
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/sendPhoto",
                    data=payload,
                    files=files
                )
            
            if response.status_code == 200:
                logger.info("Telegram 图片消息发送成功")
                return True
            else:
                logger.error(f"Telegram 图片消息发送失败：{response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram 图片消息发送异常：{e}")
            return False
    
    def send_missing_report(self, detection_result) -> bool:
        """
        发送缺集检测报告
        
        Args:
            detection_result: DetectionResult 对象
        
        Returns:
            发送是否成功
        """
        from app.detector import MissingEpisodeDetector
        
        detector = MissingEpisodeDetector()
        summary = detector.get_summary(detection_result)
        
        title = "📺 缺集检测报告"
        
        # 如果缺集数量较多，分段发送
        if len(summary) > 4000:
            # 先发送摘要
            short_summary = f"""
📊 统计信息
• 剧集总数：{detection_result.total_series}
• 有缺集的剧集：{detection_result.series_with_missing}
• 缺失总集数：{detection_result.total_missing_episodes}

⚠️ 缺集详情较多，请查看 Web 界面获取完整报告
"""
            self.send(title, short_summary)
        else:
            self.send(title, summary)
        
        return True
    
    def send_scan_complete(
        self,
        total_series: int,
        series_with_missing: int,
        total_missing: int,
        duration_seconds: float
    ) -> bool:
        """
        发送扫描完成通知
        
        Args:
            total_series: 总剧集数
            series_with_missing: 有缺集的剧集数
            total_missing: 缺失总集数
            duration_seconds: 扫描耗时
        
        Returns:
            发送是否成功
        """
        title = "✅ 扫描完成"
        
        content = f"""
📊 扫描结果

• 扫描剧集：{total_series} 部
• 发现缺集：{series_with_missing} 部
• 缺失集数：{total_missing} 集
• 耗时：{duration_seconds:.1f} 秒
"""
        
        if series_with_missing > 0:
            content += "\n🔍 查看详情：/missing"
        
        return self.send(title, content)
    
    def test(self) -> bool:
        """测试连接"""
        return self.send(
            "🧪 Telegram 通知测试",
            "这是一条测试消息，用于验证 Telegram 通知功能是否正常。\n\n如果收到此消息，说明配置正确！"
        )
    
    def get_me(self) -> Optional[Dict]:
        """获取 Bot 信息"""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/getMe")
            
            if response.status_code == 200:
                return response.json().get("result")
            return None
        except Exception as e:
            logger.error(f"获取 Bot 信息失败：{e}")
            return None


def create_telegram_notifier_from_config(config: dict) -> Optional[TelegramNotifier]:
    """从配置创建 Telegram 通知器"""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    
    if not bot_token or not chat_id:
        return None
    
    return TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        parse_mode=config.get("parse_mode", "Markdown")
    )


def setup_telegram_from_env() -> Optional[TelegramNotifier]:
    """从环境变量设置 Telegram 通知器"""
    import os
    
    enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    if not enabled:
        return None
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.warning("Telegram 配置不完整，通知功能将不可用")
        return None
    
    return TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        parse_mode=os.getenv("TELEGRAM_PARSE_MODE", "Markdown")
    )
