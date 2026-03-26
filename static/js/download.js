// ========== 下载管理页面 ==========

async function loadDownloads() {
    const container = document.getElementById('downloadGrid');
    container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>加载中...</p></div>';

    try {
        const response = await fetch('/api/download/history');
        const data = await response.json();

        if (data.status === 'success' && data.history && data.history.length > 0) {
            container.innerHTML = data.history.map(item => `
                <div class="series-card">
                    <div class="series-card-body">
                        <h3 class="series-card-title">${item.series_name}</h3>
                        <div class="series-card-meta">
                            <span><i class="fas fa-layer-group"></i> 第${item.season_number}季</span>
                            <span><i class="fas fa-clock"></i> ${new Date(item.pushed_at).toLocaleString()}</span>
                        </div>
                        <div class="series-card-tags">
                            <span class="tag season">S${item.season_number}</span>
                            <span class="tag ${item.status === 'completed' ? 'year' : 'missing'}">${item.status}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-download"></i><p>暂无下载记录</p></div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>加载失败</p></div>';
    }
}

window.refreshDownloads = async function() {
    loadDownloads();
}
