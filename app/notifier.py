"""
通知功能模块
支持 QQ、邮件等多种通知方式
参考 MoviePilot 的通知设计
"""

import os
import smtplib
import httpx
from typing import Optional, List, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """通知器基类"""
    
    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        """发送通知"""
        pass
    
    @abstractmethod
    def test(self) -> bool:
        """测试连接"""
        pass


class QQBotNotifier(BaseNotifier):
    """QQ 通知器"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        logger.info("QQ 通知器已初始化")
    
    def send(self, title: str, content: str) -> bool:
        """发送 QQ 消息"""
        try:
            message = f"📺 **{title}**\n\n{content}"
            payload = {"msgtype": "text", "text": {"content": message}}
            
            response = httpx.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("QQ 消息发送成功")
                return True
            else:
                logger.error(f"QQ 消息发送失败：{response.text}")
                return False
        except Exception as e:
            logger.error(f"QQ 消息发送异常：{e}")
            return False
    
    def test(self) -> bool:
        """测试连接"""
        return self.send("测试消息", "这是一条测试消息，用于验证 QQ 通知功能是否正常。")


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(self, smtp_server: str, smtp_port: int, 
                 username: str, password: str, recipient: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient
        logger.info(f"邮件通知器已初始化：{smtp_server}")
    
    def send(self, title: str, content: str) -> bool:
        """发送邮件"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.recipient
            msg['Subject'] = f"📺 {title}"
            
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"邮件发送成功：{self.recipient}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败：{e}")
            return False
    
    def test(self) -> bool:
        """测试连接"""
        return self.send("邮件通知测试", "这是一封测试邮件，用于验证邮件通知功能是否正常。")


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifiers: Dict[str, BaseNotifier] = {}
        logger.info("通知管理器已初始化")
    
    def add_notifier(self, name: str, notifier: BaseNotifier):
        """添加通知器"""
        self.notifiers[name] = notifier
        logger.info(f"已添加通知器：{name}")
    
    def remove_notifier(self, name: str):
        """移除通知器"""
        if name in self.notifiers:
            del self.notifiers[name]
            logger.info(f"已移除通知器：{name}")
    
    def send_all(self, title: str, content: str) -> Dict[str, bool]:
        """
        向所有通知器发送消息
        
        Returns:
            每个通知器的发送结果
        """
        results = {}
        for name, notifier in self.notifiers.items():
            results[name] = notifier.send(title, content)
        return results
    
    def send_missing_report(self, detection_result) -> Dict[str, bool]:
        """发送缺集检测报告"""
        from app.detector import MissingEpisodeDetector
        
        detector = MissingEpisodeDetector()
        summary = detector.get_summary(detection_result)
        
        title = f"缺集检测报告 - {detection_result.series_with_missing}个剧集有缺集"
        return self.send_all(title, summary)
    
    def test_all(self) -> Dict[str, bool]:
        """测试所有通知器"""
        results = {}
        for name, notifier in self.notifiers.items():
            results[name] = notifier.test()
        return results


def create_notifier_from_config(config: dict) -> Optional[BaseNotifier]:
    """从配置创建通知器"""
    notifier_type = config.get('type')
    
    if notifier_type == 'qq':
        webhook_url = config.get('webhook_url')
        if webhook_url:
            return QQBotNotifier(webhook_url)
    
    elif notifier_type == 'email':
        return EmailNotifier(
            smtp_server=config.get('smtp_server', 'smtp.gmail.com'),
            smtp_port=config.get('smtp_port', 587),
            username=config.get('username'),
            password=config.get('password'),
            recipient=config.get('recipient')
        )
    
    return None


def setup_notifiers_from_env() -> NotificationManager:
    """从环境变量设置通知器"""
    manager = NotificationManager()
    
    # QQ 通知
    qq_enabled = os.getenv('QQ_BOT_ENABLED', 'false').lower() == 'true'
    qq_webhook = os.getenv('QQ_BOT_WEBHOOK_URL')
    if qq_enabled and qq_webhook:
        manager.add_notifier('qq', QQBotNotifier(qq_webhook))
        logger.info("QQ 通知已启用")
    
    # 邮件通知
    email_enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    if email_enabled:
        notifier = EmailNotifier(
            smtp_server=os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
            username=os.getenv('EMAIL_USERNAME'),
            password=os.getenv('EMAIL_PASSWORD'),
            recipient=os.getenv('EMAIL_RECIPIENT')
        )
        manager.add_notifier('email', notifier)
        logger.info("邮件通知已启用")
    
    return manager
