"""
统计看板模块
实现缺集趋势、媒体库统计、扫描效率报表
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from loguru import logger


class StatisticsManager:
    """统计管理器"""
    
    def __init__(self, stats_path: str = "data/statistics.json"):
        """
        初始化统计管理器
        
        Args:
            stats_path: 统计数据文件路径
        """
        self.stats_path = stats_path
        self._ensure_directory()
        self._init_stats()
        logger.info(f"统计管理器已初始化：{stats_path}")
    
    def _ensure_directory(self):
        """确保目录存在"""
        db_dir = os.path.dirname(self.stats_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _init_stats(self):
        """初始化统计"""
        if not os.path.exists(self.stats_path):
            default_stats = {
                "daily_missing": {},  # {date: count}
                "library_stats": {},  # {library_id: stats}
                "scan_efficiency": [],  # [{date, duration, series_count}]
                "created_at": datetime.now().isoformat()
            }
            self._save_stats(default_stats)
    
    def _load_stats(self) -> Dict:
        """加载统计"""
        try:
            with open(self.stats_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载统计失败：{e}")
            return {}
    
    def _save_stats(self, stats: Dict):
        """保存统计"""
        with open(self.stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
    
    def update_daily_missing(self, total_missing: int):
        """更新每日缺集统计"""
        stats = self._load_stats()
        today = datetime.now().strftime("%Y-%m-%d")
        
        if "daily_missing" not in stats:
            stats["daily_missing"] = {}
        
        stats["daily_missing"][today] = total_missing
        
        # 保留最近 90 天
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        stats["daily_missing"] = {
            k: v for k, v in stats["daily_missing"].items()
            if k >= cutoff
        }
        
        self._save_stats(stats)
        logger.info(f"已更新每日缺集统计：{today} = {total_missing}")
    
    def update_library_stats(self, library_id: str, library_name: str, stats_data: Dict):
        """更新媒体库统计"""
        stats = self._load_stats()
        
        if "library_stats" not in stats:
            stats["library_stats"] = {}
        
        stats["library_stats"][library_id] = {
            "name": library_name,
            "total_series": stats_data.get("total_series", 0),
            "series_with_missing": stats_data.get("series_with_missing", 0),
            "total_missing_episodes": stats_data.get("total_missing_episodes", 0),
            "last_scan": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self._save_stats(stats)
    
    def update_scan_efficiency(self, duration_seconds: float, series_count: int):
        """更新扫描效率统计"""
        stats = self._load_stats()
        
        if "scan_efficiency" not in stats:
            stats["scan_efficiency"] = []
        
        stats["scan_efficiency"].append({
            "date": datetime.now().isoformat(),
            "duration_seconds": duration_seconds,
            "series_count": series_count,
            "avg_time_per_series": duration_seconds / series_count if series_count > 0 else 0
        })
        
        # 保留最近 100 次扫描
        stats["scan_efficiency"] = stats["scan_efficiency"][-100:]
        
        self._save_stats(stats)
    
    def get_missing_trend(self, days: int = 30) -> List[Dict]:
        """
        获取缺集趋势
        
        Args:
            days: 天数
        
        Returns:
            趋势数据列表
        """
        stats = self._load_stats()
        daily = stats.get("daily_missing", {})
        
        trend = []
        for i in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            trend.append({
                "date": date,
                "missing_count": daily.get(date, 0)
            })
        
        return trend
    
    def get_library_overview(self) -> List[Dict]:
        """获取媒体库概览"""
        stats = self._load_stats()
        libraries = stats.get("library_stats", {})
        
        return [
            {
                "id": lib_id,
                "name": lib_data.get("name", "Unknown"),
                "total_series": lib_data.get("total_series", 0),
                "series_with_missing": lib_data.get("series_with_missing", 0),
                "total_missing": lib_data.get("total_missing_episodes", 0),
                "last_scan": lib_data.get("last_scan"),
                "completeness": self._calculate_completeness(lib_data)
            }
            for lib_id, lib_data in libraries.items()
        ]
    
    def _calculate_completeness(self, lib_data: Dict) -> float:
        """计算完整率"""
        total = lib_data.get("total_series", 0)
        with_missing = lib_data.get("series_with_missing", 0)
        
        if total == 0:
            return 100.0
        
        return round(((total - with_missing) / total) * 100, 2)
    
    def get_scan_efficiency_report(self) -> Dict:
        """获取扫描效率报告"""
        stats = self._load_stats()
        scans = stats.get("scan_efficiency", [])
        
        if not scans:
            return {
                "total_scans": 0,
                "avg_duration": 0,
                "avg_time_per_series": 0,
                "fastest_scan": 0,
                "slowest_scan": 0
            }
        
        durations = [s["duration_seconds"] for s in scans]
        time_per_series = [s["avg_time_per_series"] for s in scans if s["avg_time_per_series"] > 0]
        
        return {
            "total_scans": len(scans),
            "avg_duration": round(sum(durations) / len(durations), 2),
            "avg_time_per_series": round(sum(time_per_series) / len(time_per_series), 2) if time_per_series else 0,
            "fastest_scan": round(min(durations), 2),
            "slowest_scan": round(max(durations), 2),
            "last_scan": scans[-1]["date"] if scans else None
        }
    
    def get_summary_dashboard(self) -> Dict:
        """获取摘要看板"""
        stats = self._load_stats()
        
        # 总缺集数
        daily = stats.get("daily_missing", {})
        total_missing = sum(daily.values()) if daily else 0
        
        # 媒体库统计
        libraries = stats.get("library_stats", {})
        total_series = sum(lib.get("total_series", 0) for lib in libraries.values())
        total_with_missing = sum(lib.get("series_with_missing", 0) for lib in libraries.values())
        
        # 扫描效率
        scans = stats.get("scan_efficiency", [])
        last_scan = scans[-1]["date"] if scans else None
        
        return {
            "total_missing_episodes": total_missing,
            "total_series": total_series,
            "series_with_missing": total_with_missing,
            "libraries_count": len(libraries),
            "avg_completeness": self._calculate_avg_completeness(libraries),
            "total_scans": len(scans),
            "last_scan": last_scan,
            "generated_at": datetime.now().isoformat()
        }
    
    def _calculate_avg_completeness(self, libraries: Dict) -> float:
        """计算平均完整率"""
        if not libraries:
            return 100.0
        
        completeness = [
            self._calculate_completeness(lib)
            for lib in libraries.values()
        ]
        
        return round(sum(completeness) / len(completeness), 2)
    
    def export_report(self, output_path: str) -> str:
        """
        导出统计报告
        
        Args:
            output_path: 输出文件路径
        
        Returns:
            输出文件路径
        """
        import csv
        
        dashboard = self.get_summary_dashboard()
        trend = self.get_missing_trend()
        libraries = self.get_library_overview()
        efficiency = self.get_scan_efficiency_report()
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 摘要
            writer.writerow(["=== 统计摘要 ==="])
            writer.writerow(["总缺集数", dashboard["total_missing_episodes"]])
            writer.writerow(["总剧集数", dashboard["total_series"]])
            writer.writerow(["有缺集的剧集", dashboard["series_with_missing"]])
            writer.writerow(["媒体库数量", dashboard["libraries_count"]])
            writer.writerow(["平均完整率", f"{dashboard['avg_completeness']}%"])
            writer.writerow(["总扫描次数", dashboard["total_scans"]])
            writer.writerow(["最后扫描", dashboard["last_scan"]])
            writer.writerow([])
            
            # 缺集趋势
            writer.writerow(["=== 缺集趋势 (最近 30 天) ==="])
            writer.writerow(["日期", "缺集数"])
            for item in trend:
                writer.writerow([item["date"], item["missing_count"]])
            writer.writerow([])
            
            # 媒体库统计
            writer.writerow(["=== 媒体库统计 ==="])
            writer.writerow(["媒体库", "总剧集", "有缺集", "缺集数", "完整率"])
            for lib in libraries:
                writer.writerow([
                    lib["name"],
                    lib["total_series"],
                    lib["series_with_missing"],
                    lib["total_missing"],
                    f"{lib['completeness']}%"
                ])
            writer.writerow([])
            
            # 扫描效率
            writer.writerow(["=== 扫描效率 ==="])
            writer.writerow(["总扫描次数", efficiency["total_scans"]])
            writer.writerow(["平均耗时", f"{efficiency['avg_duration']}秒"])
            writer.writerow(["平均每剧", f"{efficiency['avg_time_per_series']}秒"])
            writer.writerow(["最快扫描", f"{efficiency['fastest_scan']}秒"])
            writer.writerow(["最慢扫描", f"{efficiency['slowest_scan']}秒"])
        
        logger.info(f"统计报告已导出：{output_path}")
        return output_path


# 全局统计管理器实例
stats_manager: Optional[StatisticsManager] = None


def get_stats_manager() -> StatisticsManager:
    """获取统计管理器实例"""
    global stats_manager
    if stats_manager is None:
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        stats_path = project_root / "data" / "statistics.json"
        stats_manager = StatisticsManager(str(stats_path))
    return stats_manager
