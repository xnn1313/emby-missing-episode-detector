#!/bin/bash
# 定时进度汇报脚本 - 每 10 分钟执行一次

python3 << 'PYTHON'
import json
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path('/root/.openclaw/workspace/emby-missing-episode-detector')
TASKS_FILES = [
    PROJECT_DIR / 'TASKS.md',
    PROJECT_DIR / 'TASKS-UI-FIX.md',
    PROJECT_DIR / 'TASKS-UI-FIX2.md',
    PROJECT_DIR / 'CODEX_ANALYSIS.md'
]
CRON_FILE = PROJECT_DIR / 'cron-progress.json'

now = datetime.now()
time_str = now.strftime('%Y-%m-%d %H:%M:%S')
date_str = now.strftime('%Y-%m-%d')

# 读取所有任务文件
done = 0
in_progress = 0
pending = 0

for f in TASKS_FILES:
    if f.exists():
        content = f.read_text()
        done += content.count('✅')
        in_progress += content.count('🔄')
        pending += content.count('⏳')

total = done + in_progress + pending
progress = (done * 100 // total) if total > 0 else 0

# Git 信息
try:
    r = subprocess.run(['git', 'log', '--oneline'], cwd=PROJECT_DIR, capture_output=True, text=True, timeout=5)
    commits = [c for c in r.stdout.strip().split('\n') if c]
    git_count = len(commits)
    git_latest = commits[0][:7] if commits else 'N/A'
except:
    git_count = 0
    git_latest = 'N/A'

# 服务状态
try:
    r = subprocess.run(['pgrep', '-f', 'uvicorn main:app'], capture_output=True, timeout=2)
    service = '运行中' if r.returncode == 0 else '未运行'
except:
    service = '未知'

# 保存 JSON
data = {
    'time': time_str,
    'date': date_str,
    'tasks': {
        'done': done,
        'in_progress': in_progress,
        'pending': pending,
        'total': total,
        'progress': progress
    },
    'git': {'commits': git_count, 'latest': git_latest},
    'service': {'status': service}
}
CRON_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

print(f'[{time_str}] 📊 {done}/{total} ({progress}%) | Git: {git_count} | 服务：{service}')
PYTHON
