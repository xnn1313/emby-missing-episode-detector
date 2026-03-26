// ========== 检测历史页面 ==========

async function loadHistory() {
    const container = document.getElementById('historyList');
    container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>加载中...</p></div>';

    try {
        const response = await fetch('/api/history');
        const data = await response.json();

        if (data.status === 'success' && data.history && data.history.length > 0) {
            container.innerHTML = data.history.map(item => `
                <div class="stat-card" style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div class="stat-card-value" style="font-size: 20px;">
                                ${new Date(item.detection_time).toLocaleString()}
                            </div>
                            <div class="stat-card-label">
                                ${item.series_with_missing} 个剧集有缺集，共 ${item.total_missing_episodes} 集
                            </div>
                        </div>
                        <div class="tag year">
                            ${item.total_series} 个剧集
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-history"></i><p>暂无检测历史</p></div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>加载失败</p></div>';
    }
}
