#!/usr/bin/env python3
"""定时进度汇报脚本 - 每 10 分钟执行一次"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path("/root/.openclaw/workspace/emby-missing-episode-detector")
TASKS_FILE = PROJECT_DIR / "TASKS.md"
CRON_PROGRESS_FILE = PROJECT_DIR / "cron-progress.json"

def get_git_info():
    """获取 Git 信息"""
    try:
        commits = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True
        ).stdout.strip().split("\n")
        commits = [c for c in commits if c]
        latest = commits[0][:7] if commits else "N/A"
        return len(commits), latest
    except:
        return 0, "N/A"

def get_service_status():
    """检查服务状态"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn main:app"],
            capture_output=True
        )
        return "运行中" if result.returncode == 0 else "未运行"
    except:
        return "未知"

def parse_tasks():
    """解析任务文件"""
    if not TASKS_FILE.exists():
        return 0, 0, 0
    
    content = TASKS_FILE.read_text()
    done = content.count("✅")
    in_progress = content.count("🔄")
    pending = content.count("⏳")
    return done, in_progress, pending

def main():
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    
    done, in_progress, pending = parse_tasks()
    total = 5
    progress = (done * 100 // total) if total > 0 else 0
    
    git_commits, latest_commit = get_git_info()
    service_status = get_service_status()
    
    # 保存 JSON
    data = {
        "time": time_str,
        "date": date_str,
        "tasks": {"done": done, "in_progress": in_progress, "pending": pending, "total": total, "progress": progress},
        "git": {"commits": git_commits, "latest": latest_commit},
        "service": {"status": service_status}
    }
    
    CRON_PROGRESS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    # 输出
    print(f"[{time_str}] 进度：{done}/{total} ({progress}%) | Git: {git_commits} | 服务：{service_status}")
    
    # 追加日志
    with open("/tmp/cron-progress.log", "a") as f:
        f.write(f"{time_str} - {done}/{total} ({progress}%)\n")

if __name__ == "__main__":
    main()
