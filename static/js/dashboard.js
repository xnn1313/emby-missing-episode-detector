// ========== 仪表盘页面 ==========

let currentData = null;
let filteredData = [];
let downloadedHistory = [];

// 分页相关
let currentPage = 1;
let pageSize = 20;
let isLoading = false;
let hasMore = true;
let allCards = [];

async function loadDashboard() {
    const grid = document.getElementById('seriesGrid');
    grid.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>加载中...</p></div>';

    try {
        const [cardsRes, historyRes] = await Promise.all([
            authFetch(`/api/cards?page=${currentPage}&page_size=${pageSize}`),
            authFetch('/api/download/history')
        ]);

        const cardsData = await cardsRes.json();
        const historyData = await historyRes.json();

        downloadedHistory = historyData.status === 'success' ? (historyData.history || []) : [];
        console.log('已推送下载记录:', downloadedHistory.length);

        if (cardsData.status === 'success' && cardsData.cards && cardsData.cards.length > 0) {
            const pagination = cardsData.pagination || {};
            allCards = cardsData.cards;
            currentData = cardsData.cards;
            filteredData = cardsData.cards;
            hasMore = pagination.has_more || false;

            updateStatsWithPagination(cardsData.cards, pagination);
            renderCards(cardsData.cards, grid);
            setupInfiniteScroll();
        } else {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-tv"></i>
                    <p>暂无检测结果</p>
                    <button class="btn btn-primary" style="margin-top: 20px;" onclick="runDetection(this)">
                        <i class="fas fa-play"></i>
                        开始检测
                    </button>
                </div>
            `;
        }
    } catch (error) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>加载失败：${error.message}</p>
            </div>
        `;
    }
}

function updateStatsWithPagination(cards, pagination) {
    const total = pagination.total || cards.length;
    const missing = pagination.total || cards.length;

    const episodes = cards.reduce((sum, c) => {
        const count = Array.isArray(c.missing_episodes) ? c.missing_episodes.length : 0;
        return sum + count;
    }, 0);

    if (pagination.total && pagination.page && pagination.page_size) {
        const avgMissingPerCard = episodes / cards.length;
        const estimatedTotal = Math.round(avgMissingPerCard * pagination.total);
        document.getElementById('statEpisodes').textContent = estimatedTotal;
    } else {
        document.getElementById('statEpisodes').textContent = episodes;
    }

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statMissing').textContent = missing;
    document.getElementById('missingBadge').textContent = missing;

    updateSeasonFilter(cards);
}

function updateSeasonFilter(cards) {
    const seasonFilter = document.getElementById('filterSeason');
    const seasons = new Set(cards.map(c => c.season).filter(s => s));
    const currentOptions = Array.from(seasonFilter.options).map(o => o.value);

    const hasAll = currentOptions.includes('');
    const seasonValues = Array.from(seasons).map(String);
    const needsUpdate = !hasAll || seasonValues.some(s => !currentOptions.includes(s));

    if (!needsUpdate) return;

    seasonFilter.innerHTML = '<option value="">全部季</option>';
    Array.from(seasons).sort((a, b) => a - b).forEach(season => {
        const option = document.createElement('option');
        option.value = season;
        option.textContent = `第${season}季`;
        seasonFilter.appendChild(option);
    });
}

function buildCardHtml(card, isDownloaded) {
    const missingEps = Array.isArray(card.missing_episodes) ? card.missing_episodes : [];
    const hasMissing = missingEps.length > 0;
    const posterUrl = card.poster_url || card.poster || '';

    return `
    <div class="series-card" data-name="${card.series_name || ''}" data-year="${card.year || ''}" data-missing="${missingEps.length}">
        <div class="series-card-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            ${posterUrl
                ? `<img src="${posterUrl}" alt="${card.series_name}" crossorigin="anonymous" onload="this.style.opacity='1'" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
                : ''}
            <div class="placeholder" style="${posterUrl ? 'display:none' : 'display:flex'}; align-items:center; justify-content:center; height:100%;">
                <i class="fas fa-tv" style="font-size:64px; opacity:0.5;"></i>
            </div>
            <div class="series-card-badge ${hasMissing ? 'missing' : 'complete'}">
                ${hasMissing ? '缺集' : '完整'}
            </div>
        </div>
        <div class="series-card-body">
            <h3 class="series-card-title" title="${card.series_name || ''}">${card.series_name || '未知剧集'}</h3>
            <div class="series-card-meta">
                <span><i class="fas fa-calendar"></i> ${card.year || '未知'}</span>
                <span><i class="fas fa-layer-group"></i> 第${card.season || 1}季</span>
            </div>
            <div class="series-card-tags">
                <span class="tag season">S${card.season || 1}</span>
                ${card.year ? `<span class="tag year">${card.year}</span>` : ''}
                ${hasMissing ? `<span class="tag missing">缺失 ${missingEps.length} 集</span>` : ''}
            </div>
            ${hasMissing ? `
                <div class="series-card-missing">
                    <div class="series-card-missing-title">
                        <i class="fas fa-exclamation-triangle"></i> 缺失剧集
                    </div>
                    <div class="missing-episodes">
                        ${missingEps.slice(0, 10).map(ep => `<span class="missing-ep">E${ep}</span>`).join('')}
                        ${missingEps.length > 10 ? `<span class="missing-ep">+${missingEps.length - 10}</span>` : ''}
                    </div>
                </div>
            ` : ''}
            <div class="series-card-actions">
                ${!hasMissing
                    ? `<button class="btn btn-outline" disabled style="width:100%; cursor:not-allowed;">
                        <i class="fas fa-check"></i>
                        已完整
                       </button>`
                    : isDownloaded
                        ? `<button class="btn btn-outline" disabled style="width:100%; cursor:not-allowed;">
                            <i class="fas fa-check-circle"></i>
                            已推送
                           </button>`
                        : `<button class="btn btn-primary download-btn" style="width:100%;" data-series-id="${card.series_id || ''}" data-series-name="${(card.series_name || '').replace(/"/g, '&quot;')}" data-season="${card.season || 1}">
                            <i class="fas fa-download"></i>
                            推送下载
                           </button>`
                }
            </div>
            <button class="btn btn-outline hdhive-btn" style="width:100%;margin-top:8px;justify-content:center;" data-series-id="${card.series_id || ''}" data-series-name="${(card.series_name || '').replace(/"/g, '&quot;')}" data-tmdb-id="${card.tmdb_id || ''}" title="查询 HDHive 资源">
                <i class="fas fa-search"></i> 查询 HDHive
            </button>
        </div>
    </div>
    `;
}

function renderCards(cards, container, append = false) {
    if (!cards || cards.length === 0) {
        if (!append) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>没有数据</p></div>';
        }
        return;
    }

    const html = cards.map(card => {
        const isDownloaded = downloadedHistory.some(h =>
            h.series_id === card.series_id && h.season_number === card.season
        );
        console.log('Card:', card.series_name, 'S' + card.season, 'downloaded:', isDownloaded);
        return buildCardHtml(card, isDownloaded);
    }).join('');

    if (append) {
        container.insertAdjacentHTML('beforeend', html);
    } else {
        container.innerHTML = html;
    }
}

function setupInfiniteScroll() {
    window.onscroll = null;
    window.onscroll = function() {
        const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
        const clientHeight = document.documentElement.clientHeight || window.innerHeight;

        if (scrollTop + clientHeight >= scrollHeight - 300) {
            if (!isLoading && hasMore) {
                loadMoreCards();
            }
        }
    };
}

async function loadMoreCards() {
    if (isLoading || !hasMore) return;

    isLoading = true;
    currentPage++;

    const grid = document.getElementById('seriesGrid');
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loadingMore';
    loadingDiv.className = 'loading';
    loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i><p>加载中...</p>';
    grid.appendChild(loadingDiv);

    try {
        const response = await authFetch(`/api/cards?page=${currentPage}&page_size=${pageSize}`);
        const data = await response.json();

        loadingDiv.remove();

        if (data.status === 'success' && data.cards && data.cards.length > 0) {
            const pagination = data.pagination || {};
            allCards = [...allCards, ...data.cards];
            hasMore = pagination.has_more || false;

            const html = data.cards.map(card => {
                const isDownloaded = downloadedHistory.some(h =>
                    h.series_id === card.series_id && h.season_number === card.season
                );
                return buildCardHtml(card, isDownloaded);
            }).join('');

            grid.insertAdjacentHTML('beforeend', html);

            if (!hasMore) {
                const endDiv = document.createElement('div');
                endDiv.className = 'loading';
                endDiv.innerHTML = '<p>已经到底啦~</p>';
                grid.appendChild(endDiv);
            }
        } else {
            hasMore = false;
        }
    } catch (error) {
        console.error('加载更多失败:', error);
        loadingDiv.innerHTML = '<p>加载失败</p>';
    } finally {
        isLoading = false;
    }
}

window.filterSeries = function() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const season = document.getElementById('filterSeason').value;
    const status = document.getElementById('filterStatus').value;
    const sortBy = document.getElementById('sortBy').value;

    let filtered = currentData || [];

    if (search) {
        filtered = filtered.filter(c => (c.series_name || '').toLowerCase().includes(search));
    }
    if (season) {
        filtered = filtered.filter(c => (c.season || 1) == season);
    }
    if (status === 'missing') {
        filtered = filtered.filter(c => c.missing_episodes && c.missing_episodes.length > 0);
    } else if (status === 'complete') {
        filtered = filtered.filter(c => !c.missing_episodes || c.missing_episodes.length === 0);
    }

    if (sortBy === 'name') {
        filtered.sort((a, b) => (a.series_name || '').localeCompare(b.series_name || ''));
    } else if (sortBy === 'year') {
        filtered.sort((a, b) => (b.year || '0').localeCompare(a.year || '0'));
    } else if (sortBy === 'missing') {
        filtered.sort((a, b) => (b.missing_episodes?.length || 0) - (a.missing_episodes?.length || 0));
    }

    filteredData = filtered;
    renderCards(filtered, document.getElementById('seriesGrid'));
}

window.runDetection = async function(btn) {
    const actionBtn = btn || document.querySelector('#page-dashboard .toolbar-actions .btn-primary, #page-dashboard .empty-state .btn-primary');
    if (!actionBtn) {
        alert('检测按钮未找到，请刷新页面后重试');
        return;
    }

    const originalHtml = actionBtn.innerHTML;
    actionBtn.disabled = true;
    actionBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检测中...';

    try {
        const response = await fetch('/api/detect');
        const data = await response.json();

        if (response.ok && data.status === 'success') {
            alert(`检测完成！\n\n总剧集：${data.stats.total_series}\n有缺集：${data.stats.series_with_missing}\n缺失总集数：${data.stats.total_missing_episodes}`);
            loadDashboard();
        } else {
            alert('检测失败：' + (data.message || data.detail || '未知错误'));
        }
    } catch (error) {
        alert('检测失败：' + error.message);
    } finally {
        actionBtn.disabled = false;
        actionBtn.innerHTML = originalHtml || '<i class="fas fa-play"></i> 开始检测';
    }
}

async function pushDownload(seriesId, seriesName, season, btn) {
    console.log('推送下载:', { seriesId, seriesName, season });

    const cardData = allCards.find(c => c.series_id === seriesId && c.season === season);
    const missingEps = cardData && cardData.missing_episodes ? cardData.missing_episodes : [];

    if (!seriesId || !seriesName) {
        alert('错误：剧集信息不完整');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 推送中...';

    try {
        const response = await authFetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                series_id: seriesId,
                series_name: seriesName,
                season: season,
                episodes: missingEps
            })
        });

        const data = await response.json();

        if (response.ok && data.status === 'success') {
            alert('✅ 推送成功！\n\n剧集：' + seriesName + ' 第' + season + '季\nMoviePilot 将自动下载缺失剧集');
            btn.innerHTML = '<i class="fas fa-check"></i> 已推送';
            btn.disabled = true;
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline');
        } else {
            alert('❌ 推送失败：' + (data.detail || data.message || '未知错误'));
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> 推送下载';
        }
    } catch (error) {
        console.error('推送异常:', error);
        alert('❌ 推送异常：' + error.message);
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> 推送下载';
    }
}

window.refreshData = async function() {
    currentPage = 1;
    hasMore = true;
    allCards = [];
    const grid = document.getElementById('seriesGrid');
    grid.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>加载中...</p></div>';
    loadDashboard();
}
