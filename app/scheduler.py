"""
定时任务调度器模块
支持周期性自动检测
参考 MoviePilot 的定时任务设计
"""

import os
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.tasks: Dict[str, Dict] = {}
        logger.info("任务调度器已初始化")
    
    def start(self):
        """启动调度器"""
        self.scheduler.start()
        logger.info("任务调度器已启动")
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        self.scheduler.shutdown(wait=wait)
        logger.info("任务调度器已关闭")
    
    def add_interval_task(
        self,
        name: str,
        func: Callable,
        minutes: int = 10,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None
    ):
        """
        添加间隔任务
        
        Args:
            name: 任务名称
            func: 任务函数
            minutes: 间隔分钟数
            args: 函数参数
            kwargs: 函数关键字参数
        """
        trigger = IntervalTrigger(minutes=minutes)
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=name,
            name=name,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True
        )
        self.tasks[name] = {
            'type': 'interval',
            'minutes': minutes,
            'func': func.__name__,
            'created': datetime.now()
        }
        logger.info(f"已添加间隔任务：{name} (每{minutes}分钟)")
    
    def add_cron_task(
        self,
        name: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        day_of_week: str = '*',
        args: Optional[list] = None,
        kwargs: Optional[dict] = None
    ):
        """
        添加 Cron 任务
        
        Args:
            name: 任务名称
            func: 任务函数
            hour: 小时 (0-23)
            minute: 分钟 (0-59)
            day_of_week: 星期几 (0-6 或 mon-sun)
            args: 函数参数
            kwargs: 函数关键字参数
        """
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week
        )
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=name,
            name=name,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True
        )
        self.tasks[name] = {
            'type': 'cron',
            'schedule': f'{hour}:{minute:02d} (周{day_of_week})',
            'func': func.__name__,
            'created': datetime.now()
        }
        logger.info(f"已添加 Cron 任务：{name} ({hour}:{minute:02d})")
    
    def remove_task(self, name: str):
        """移除任务"""
        if name in self.tasks:
            self.scheduler.remove_job(name)
            del self.tasks[name]
            logger.info(f"已移除任务：{name}")
    
    def get_task_status(self, name: str) -> Optional[Dict]:
        """获取任务状态"""
        try:
            job = self.scheduler.get_job(name)
            if job:
                return {
                    'name': name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'info': self.tasks.get(name, {})
                }
            return None
        except Exception as e:
            logger.error(f"获取任务状态失败 {name}: {e}")
            return None
    
    def get_all_tasks_status(self) -> Dict[str, Dict]:
        """获取所有任务状态"""
        status = {}
        for name in self.tasks:
            status[name] = self.get_task_status(name)
        return status
    
    def run_task_now(self, name: str):
        """立即运行任务"""
        try:
            job = self.scheduler.get_job(name)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"任务 {name} 已触发立即执行")
            else:
                logger.warning(f"任务不存在：{name}")
        except Exception as e:
            logger.error(f"触发任务失败 {name}: {e}")


class DetectionScheduler:
    """检测任务调度器 - 封装缺集检测的定时执行"""
    
    def __init__(self, emby_client, detector, notifier_manager=None):
        self.emby_client = emby_client
        self.detector = detector
        self.notifier_manager = notifier_manager
        self.scheduler = TaskScheduler()
        self.last_result = None
        self.last_run = None
        self.run_count = 0
        logger.info("检测任务调度器已初始化")
    
    def start_auto_detection(self, interval_minutes: int = 60):
        """
        启动自动检测
        
        Args:
            interval_minutes: 检测间隔（分钟）
        """
        self.scheduler.add_interval_task(
            name='auto_detection',
            func=self._run_detection,
            minutes=interval_minutes
        )
        self.scheduler.start()
        logger.info(f"自动检测已启动 (间隔：{interval_minutes}分钟)")
    
    def _run_detection(self):
        """执行检测任务（内部方法）"""
        try:
            logger.info("开始定时检测...")
            self.last_run = datetime.now()
            self.run_count += 1
            
            # 运行检测
            result = self.detector.detect(self.emby_client)
            self.last_result = result
            
            # 发送通知（如果有缺集）
            if self.notifier_manager and result.series_with_missing > 0:
                self.notifier_manager.send_missing_report(result)
            
            logger.info(
                f"定时检测完成：{result.series_with_missing}/{result.total_series} "
                f"个剧集有缺集，共缺失 {result.total_missing_episodes} 集"
            )
            
        except Exception as e:
            logger.error(f"定时检测失败：{e}")
    
    def run_now(self):
        """立即运行检测"""
        self._run_detection()
    
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'run_count': self.run_count,
            'last_result': {
                'total_series': self.last_result.total_series if self.last_result else 0,
                'series_with_missing': self.last_result.series_with_missing if self.last_result else 0,
                'total_missing_episodes': self.last_result.total_missing_episodes if self.last_result else 0
            } if self.last_result else None,
            'scheduler_status': self.scheduler.get_all_tasks_status()
        }
    
    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
        logger.info("检测任务调度器已关闭")
