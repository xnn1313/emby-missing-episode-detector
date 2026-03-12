"""
扫描中心模块
实现扫描任务管理、历史记录、定时配置
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
from loguru import logger


class ScanTask:
    """扫描任务"""
    
    def __init__(
        self,
        task_id: str,
        task_type: str = "manual",  # manual, scheduled
        status: str = "pending",  # pending, running, completed, failed
        created_at: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.status = status
        self.created_at = created_at or datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: int = 0  # 0-100
        self.total_series: int = 0
        self.processed_series: int = 0
        self.found_missing: int = 0
        self.error_message: Optional[str] = None
        self.result_summary: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "total_series": self.total_series,
            "processed_series": self.processed_series,
            "found_missing": self.found_missing,
            "error_message": self.error_message,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            )
        }


class ScanManager:
    """扫描任务管理器"""
    
    def __init__(self, history_path: str = "data/scan_history.json"):
        """
        初始化扫描管理器
        
        Args:
            history_path: 历史记录文件路径
        """
        self.history_path = history_path
        self._ensure_directory()
        self._init_history()
        self.current_task: Optional[ScanTask] = None
        self.scan_callback: Optional[Callable] = None
        logger.info("扫描管理器已初始化")
    
    def _ensure_directory(self):
        """确保目录存在"""
        db_dir = os.path.dirname(self.history_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _init_history(self):
        """初始化历史记录"""
        if not os.path.exists(self.history_path):
            self._save_history({"tasks": [], "created_at": datetime.now().isoformat()})
    
    def _load_history(self) -> Dict:
        """加载历史记录"""
        try:
            with open(self.history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载扫描历史失败：{e}")
            return {"tasks": []}
    
    def _save_history(self, data: Dict):
        """保存历史记录"""
        with open(self.history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def create_task(self, task_type: str = "manual") -> ScanTask:
        """创建扫描任务"""
        import secrets
        task = ScanTask(
            task_id=secrets.token_urlsafe(16),
            task_type=task_type
        )
        self.current_task = task
        
        # 保存到历史
        history = self._load_history()
        history["tasks"].append(task.to_dict())
        self._save_history(history)
        
        logger.info(f"扫描任务已创建：{task.task_id} (类型：{task_type})")
        return task
    
    def start_task(self, total_series: int):
        """开始任务"""
        if not self.current_task:
            logger.error("没有当前任务")
            return
        
        self.current_task.status = "running"
        self.current_task.started_at = datetime.now()
        self.current_task.total_series = total_series
        self._update_task_in_history()
        logger.info(f"扫描任务已开始：{self.current_task.task_id}")
    
    def update_progress(self, processed: int, found_missing: int):
        """更新进度"""
        if not self.current_task:
            return
        
        self.current_task.processed_series = processed
        self.current_task.found_missing = found_missing
        
        if self.current_task.total_series > 0:
            self.current_task.progress = int(
                (processed / self.current_task.total_series) * 100
            )
        
        self._update_task_in_history()
    
    def complete_task(self, result_summary: Dict):
        """完成任务"""
        if not self.current_task:
            return
        
        self.current_task.status = "completed"
        self.current_task.completed_at = datetime.now()
        self.current_task.progress = 100
        self.current_task.result_summary = result_summary
        
        self._update_task_in_history()
        logger.info(
            f"扫描任务已完成：{self.current_task.task_id} "
            f"(耗时：{self.current_task.to_dict()['duration_seconds']:.2f}秒)"
        )
        
        self.current_task = None
    
    def fail_task(self, error_message: str):
        """失败任务"""
        if not self.current_task:
            return
        
        self.current_task.status = "failed"
        self.current_task.completed_at = datetime.now()
        self.current_task.error_message = error_message
        
        self._update_task_in_history()
        logger.error(f"扫描任务失败：{self.current_task.task_id} - {error_message}")
        
        self.current_task = None
    
    def _update_task_in_history(self):
        """更新历史记录中的任务"""
        if not self.current_task:
            return
        
        history = self._load_history()
        for i, task in enumerate(history["tasks"]):
            if task["task_id"] == self.current_task.task_id:
                history["tasks"][i] = self.current_task.to_dict()
                break
        self._save_history(history)
    
    def get_task_history(self, limit: int = 50) -> List[Dict]:
        """获取任务历史"""
        history = self._load_history()
        tasks = sorted(
            history["tasks"],
            key=lambda x: x["created_at"],
            reverse=True
        )
        return tasks[:limit]
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """根据 ID 获取任务"""
        history = self._load_history()
        for task in history["tasks"]:
            if task["task_id"] == task_id:
                return task
        return None
    
    def get_current_task(self) -> Optional[Dict]:
        """获取当前任务状态"""
        if self.current_task:
            return self.current_task.to_dict()
        return None
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        history = self._load_history()
        tasks = history["tasks"]
        
        if not tasks:
            return {
                "total_scans": 0,
                "completed_scans": 0,
                "failed_scans": 0,
                "avg_duration": 0,
                "last_scan": None
            }
        
        completed = [t for t in tasks if t["status"] == "completed"]
        failed = [t for t in tasks if t["status"] == "failed"]
        
        avg_duration = 0
        if completed:
            durations = [t.get("duration_seconds") for t in completed if t.get("duration_seconds")]
            if durations:
                avg_duration = sum(durations) / len(durations)
        
        last_scan = tasks[0]["created_at"] if tasks else None
        
        return {
            "total_scans": len(tasks),
            "completed_scans": len(completed),
            "failed_scans": len(failed),
            "avg_duration": round(avg_duration, 2),
            "last_scan": last_scan
        }
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        history = self._load_history()
        cutoff = datetime.now() - timedelta(days=days)
        
        original_count = len(history["tasks"])
        history["tasks"] = [
            t for t in history["tasks"]
            if datetime.fromisoformat(t["created_at"]) > cutoff
        ]
        
        self._save_history(history)
        deleted = original_count - len(history["tasks"])
        
        if deleted > 0:
            logger.info(f"已清理 {deleted} 条旧扫描记录")
        
        return deleted


# 全局扫描管理器实例
scan_manager: Optional[ScanManager] = None


def get_scan_manager() -> ScanManager:
    """获取扫描管理器实例"""
    global scan_manager
    if scan_manager is None:
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        history_path = project_root / "data" / "scan_history.json"
        scan_manager = ScanManager(str(history_path))
    return scan_manager
