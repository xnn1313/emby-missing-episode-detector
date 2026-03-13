"""
数据持久化模块
SQLite 存储检测结果和历史记录
"""

import os
import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from loguru import logger
from contextlib import contextmanager


class Database:
    """SQLite 数据库管理类"""
    
    def __init__(self, db_path: str = "data/emby_detector.db"):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_directory()
        self._init_schema()
        logger.info(f"数据库已初始化：{db_path}")
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"创建数据库目录：{db_dir}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_schema(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检测历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detection_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detection_time TIMESTAMP NOT NULL,
                    total_series INTEGER NOT NULL,
                    series_with_missing INTEGER NOT NULL,
                    total_missing_episodes INTEGER NOT NULL,
                    duration_seconds REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 剧集缺集表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS missing_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detection_id INTEGER NOT NULL,
                    series_id TEXT NOT NULL,
                    series_name TEXT NOT NULL,
                    season_number INTEGER NOT NULL,
                    episode_numbers TEXT NOT NULL,
                    poster_url TEXT DEFAULT '',
                    year TEXT DEFAULT '',
                    status TEXT DEFAULT 'ongoing',
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (detection_id) REFERENCES detection_history(id)
                )
            ''')
            
            # 添加索引（如果不存在）
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_missing_series ON missing_episodes(series_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_missing_detection ON missing_episodes(detection_id)')
            except Exception as e:
                logger.debug(f"索引已存在或创建失败：{e}")
            
            # 剧集信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS series_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_id TEXT UNIQUE NOT NULL,
                    series_name TEXT NOT NULL,
                    series_path TEXT,
                    total_seasons INTEGER,
                    total_episodes INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 下载历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_id TEXT NOT NULL,
                    series_name TEXT NOT NULL,
                    season_number INTEGER,
                    episode_numbers TEXT,
                    moviepilot_task_id TEXT,
                    status TEXT DEFAULT 'pending',
                    pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_detection_time ON detection_history(detection_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_series_id ON missing_episodes(series_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_detected_at ON missing_episodes(detected_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_status ON download_history(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_series_season ON download_history(series_id, season_number)')
            
            conn.commit()
            logger.info("数据库表结构已初始化")
    
    def save_detection_result(self, result) -> int:
        """
        保存检测结果
        
        Args:
            result: DetectionResult 对象
        
        Returns:
            检测记录 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 插入检测历史
            cursor.execute('''
                INSERT INTO detection_history 
                (detection_time, total_series, series_with_missing, total_missing_episodes)
                VALUES (?, ?, ?, ?)
            ''', (
                result.detection_time,
                result.total_series,
                result.series_with_missing,
                result.total_missing_episodes
            ))
            
            detection_id = cursor.lastrowid
            
            # 插入缺集详情
            for series in result.series:
                if series.missing_episodes_count > 0:
                    for season in series.seasons:
                        if season.missing_episodes:
                            cursor.execute('''
                                INSERT INTO missing_episodes 
                                (detection_id, series_id, series_name, season_number, episode_numbers, poster_url, year, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                detection_id,
                                series.series_id,
                                series.series_name,
                                season.season_number,
                                json.dumps(season.missing_episodes),
                                series.poster_url or '',
                                series.year or '',
                                series.status or 'ongoing'
                            ))
            
            conn.commit()
            logger.info(f"已保存检测结果 ID: {detection_id}")
            return detection_id
    
    def get_detection_history(self, limit: int = 50) -> List[Dict]:
        """
        获取检测历史
        
        Args:
            limit: 返回记录数限制
        
        Returns:
            检测历史列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM detection_history 
                ORDER BY detection_time DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_missing_episodes_by_series(self, series_id: str) -> List[Dict]:
        """
        获取指定剧集的缺集记录
        
        Args:
            series_id: 剧集 ID
        
        Returns:
            缺集记录列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM missing_episodes 
                WHERE series_id = ?
                ORDER BY season_number, detected_at DESC
            ''', (series_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_missing_episodes(self, limit: int = 100) -> List[Dict]:
        """
        获取最新的缺集记录
        
        Args:
            limit: 返回记录数限制
        
        Returns:
            缺集记录列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.*, d.detection_time
                FROM missing_episodes m
                JOIN detection_history d ON m.detection_id = d.id
                ORDER BY d.detection_time DESC, m.season_number
                LIMIT ?
            ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                record = dict(row)
                record['episode_numbers'] = json.loads(record['episode_numbers'])
                results.append(record)
            
            return results
    
    def save_download_history(self, series_id: str, series_name: str,
                             season_number: int, episode_numbers: List[int],
                             moviepilot_task_id: Optional[str] = None) -> int:
        """
        保存下载历史记录
        
        Args:
            series_id: 剧集 ID
            series_name: 剧集名称
            season_number: 季数
            episode_numbers: 缺失集数列表
            moviepilot_task_id: MoviePilot 任务 ID
        
        Returns:
            记录 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO download_history 
                (series_id, series_name, season_number, episode_numbers, moviepilot_task_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                series_id,
                series_name,
                season_number,
                json.dumps(episode_numbers),
                moviepilot_task_id
            ))
            return cursor.lastrowid
    
    def update_download_status(self, record_id: int, status: str, 
                              task_id: Optional[str] = None) -> bool:
        """
        更新下载状态
        
        Args:
            record_id: 记录 ID
            status: 新状态 (pending/downloading/completed/failed)
            task_id: MoviePilot 任务 ID
        
        Returns:
            是否成功
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute('''
                    UPDATE download_history 
                    SET status = ?, moviepilot_task_id = ?
                    WHERE id = ?
                ''', (status, task_id, record_id))
            else:
                cursor.execute('''
                    UPDATE download_history 
                    SET status = ?
                    WHERE id = ?
                ''', (status, record_id))
            return cursor.rowcount > 0
    
    def get_download_history(self, series_id: Optional[str] = None, 
                            status: Optional[str] = None,
                            limit: int = 100) -> List[Dict]:
        """
        获取下载历史
        
        Args:
            series_id: 剧集 ID（可选）
            status: 状态过滤（可选）
            limit: 返回记录数限制
        
        Returns:
            下载历史列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM download_history WHERE 1=1'
            params = []
            
            if series_id:
                query += ' AND series_id = ?'
                params.append(series_id)
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                record = dict(row)
                record['episode_numbers'] = json.loads(record['episode_numbers'])
                results.append(record)
            
            return results
    
    def get_latest_detection_result(self, limit: int = 1) -> List[Dict]:
        """
        获取最近的检测结果
        
        Args:
            limit: 返回记录数限制
        
        Returns:
            检测结果列表（包含缺集详情）
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取最近的检测历史
            cursor.execute('''
                SELECT * FROM detection_history 
                ORDER BY detection_time DESC 
                LIMIT ?
            ''', (limit,))
            
            history_rows = cursor.fetchall()
            if not history_rows:
                return []
            
            results = []
            for history in history_rows:
                history_dict = dict(history)
                
                # 获取该次检测的缺集详情
                cursor.execute('''
                    SELECT series_id, series_name, season_number, episode_numbers, poster_url, year, status
                    FROM missing_episodes
                    WHERE detection_id = ?
                    ORDER BY series_name, season_number
                ''', (history_dict['id'],))
                
                missing_details = []
                for row in cursor.fetchall():
                    record = dict(row)
                    record['episode_numbers'] = json.loads(record['episode_numbers'])
                    missing_details.append(record)
                
                history_dict['missing_details'] = missing_details
                results.append(history_dict)
            
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 总检测次数
            cursor.execute('SELECT COUNT(*) FROM detection_history')
            total_detections = cursor.fetchone()[0]
            
            # 平均缺集数
            cursor.execute('SELECT AVG(total_missing_episodes) FROM detection_history')
            avg_missing = cursor.fetchone()[0] or 0
            
            # 最近检测时间
            cursor.execute('SELECT MAX(detection_time) FROM detection_history')
            last_detection = cursor.fetchone()[0]
            
            return {
                'total_detections': total_detections,
                'average_missing_episodes': round(avg_missing, 2),
                'last_detection': last_detection
            }
    
    def cleanup_old_records(self, days: int = 30):
        """
        清理旧记录
        
        Args:
            days: 保留最近 N 天的记录
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 删除旧的检测历史（级联删除缺集记录）
            cursor.execute('''
                DELETE FROM detection_history 
                WHERE detection_time < ?
            ''', (cutoff_date.isoformat(),))
            
            deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"已清理 {deleted} 条旧记录")
            return deleted
    
    def export_to_csv(self, output_path: str) -> int:
        """
        导出数据为 CSV
        
        Args:
            output_path: 输出文件路径
        
        Returns:
            导出记录数
        """
        import csv
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.series_name, m.season_number, m.episode_numbers, 
                       d.detection_time, d.total_missing_episodes
                FROM missing_episodes m
                JOIN detection_history d ON m.detection_id = d.id
                ORDER BY d.detection_time DESC
            ''')
            
            rows = cursor.fetchall()
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['剧集名称', '季号', '缺失集数', '检测时间', '总缺集数'])
                
                for row in rows:
                    episodes = json.loads(row[2])
                    writer.writerow([
                        row[0],
                        row[1],
                        ', '.join(map(str, episodes)),
                        row[3],
                        row[4]
                    ])
            
            logger.info(f"已导出 {len(rows)} 条记录到 {output_path}")
            return len(rows)


# 全局数据库实例
db: Optional[Database] = None


def get_database() -> Database:
    """获取数据库实例"""
    global db
    if db is None:
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'emby_detector.db'
        )
        db = Database(db_path)
    return db
