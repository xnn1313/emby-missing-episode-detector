#!/bin/bash
# 定时进度汇报脚本 - 每 10 分钟执行一次

python3 -c "
import json
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path('/root/.openclaw/workspace/emby-missing-episode-detector')
TASKS_FILE = PROJECT_DIR / 'TASKS.md'
CRON_FILE = PROJECT_DIR / 'cron-progress.json'

now = datetime.now()
time_str = now.strftime('%Y-%m-%d %H:%M:%S')
date_str = now.strftime('%Y-%m-%d')

content = TASKS_FILE.read_text() if TASKS_FILE.exists() else ''
done = content.count('✅')
in_progress = content.count('🔄')
pending = content.count('⏳')
total = 5
progress = (done * 100 // total) if total > 0 else 0

# Git 信息
import subprocess
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
data = {'time': time_str, 'date': date_str, 'tasks': {'done': done, 'total': total, 'progress': progress}, 'git': {'commits': git_count}, 'service': service}
CRON_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

print(f'[{time_str}] 📊 {done}/{total} ({progress}%) | Git: {git_count} | 服务：{service}')
" 2>/dev/null || echo "[$(date '+%Y-%m-%d %H:%M:%S')] 进度检查失败"
