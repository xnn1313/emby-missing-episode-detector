// ========== TMDB Feed 页面 ==========

let tmdbFeedPage = 1;
let tmdbFeedHasMore = true;
let tmdbFeedLoading = false;
let tmdbFeedItems = [];

function renderTmdbFeedCards(items, container) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>没有数据</p></div>';
        return;
    }

    const html = list.map(item => {
        const tmdbId = item?.id;
        const title = item?.name || item?.original_name || '未知剧集';
        const overview = item?.overview || '';
        const firstAir = item?.first_air_date || '';
        const year = item?.year || (firstAir ? String(firstAir).slice(0, 4) : '');
        const posterUrl = item?.poster_url || '';
        const vote = item?.vote_average ? Number(item.vote_average).toFixed(1) : '';
        const inLib = !!item?.in_library;

        return `
        <div class="series-card" data-name="${String(title).replace(/"/g, '&quot;')}" data-year="${String(year).replace(/"/g, '&quot;')}" data-missing="0">
            <div class="series-card-header" style="background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);">
                ${posterUrl
                    ? `<img src="${posterUrl}" alt="${String(title).replace(/"/g, '&quot;')}" crossorigin="anonymous" onload="this.style.opacity='1'" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
                    : ''}
                <div class="placeholder" style="${posterUrl ? 'display:none' : 'display:flex'}; align-items:center; justify-content:center; height:100%;">
                    <i class="fas fa-fire" style="font-size:64px; opacity:0.45;"></i>
                </div>
                <div class="series-card-badge complete">TMDB</div>
            </div>
            <div class="series-card-body">
                <h3 class="series-card-title" title="${String(title).replace(/"/g, '&quot;')}">${title}</h3>
                <div class="series-card-meta">
                    <span><i class="fas fa-calendar"></i> ${firstAir ? firstAir : (year || '未知')}</span>
                    <span><i class="fas fa-star"></i> ${vote || '-'}</span>
                </div>
                <div class="series-card-tags">
                    ${year ? `<span class="tag year">${year}</span>` : ''}
                    <span class="tag season">TMDB ${tmdbId || ''}</span>
                    ${inLib ? `<span class="tag year"><i class="fas fa-database"></i> 已入库</span>` : `<span class="tag missing"><i class="fas fa-database"></i> 未入库</span>`}
                </div>
                ${overview ? `
                    <div style="color:#94a3b8;font-size:13px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-top:10px;">
                        ${escapeHtml(overview)}
                    </div>
                ` : ''}
                <div class="series-card-actions" style="margin-top:12px;">
                    <button class="btn btn-outline tmdb-hdhive-btn" style="width:100%;justify-content:center;" data-tmdb-id="${tmdbId || ''}" data-series-name="${String(title).replace(/"/g, '&quot;')}">
                        <i class="fas fa-search"></i> 查询 HDHive
                    </button>
                </div>
            </div>
        </div>
        `;
    }).join('');

    container.innerHTML = html;
}

window.filterTmdbFeed = function() {
    const input = document.getElementById('tmdbSearchInput');
    const keyword = (input?.value || '').trim().toLowerCase();
    const container = document.getElementById('tmdbGrid');
    if (!container) return;

    if (!keyword) {
        renderTmdbFeedCards(tmdbFeedItems, container);
        return;
    }

    const filtered = (tmdbFeedItems || []).filter(item => {
        const hay = [
            item?.name || '',
            item?.original_name || '',
            item?.overview || '',
            item?.first_air_date || '',
        ].join(' ').toLowerCase();
        return hay.includes(keyword);
    });
    renderTmdbFeedCards(filtered, container);
}

window.loadTmdbFeed = async function(reset = true) {
    const container = document.getElementById('tmdbGrid');
    const loadMoreBtn = document.getElementById('tmdbLoadMoreBtn');
    if (!container) return;
    if (tmdbFeedLoading) return;

    const ok = await ensureAuthenticated(false);
    if (!ok) return;

    const feed = (document.getElementById('tmdbFeed')?.value || 'on_the_air').trim();

    if (reset) {
        tmdbFeedPage = 1;
        tmdbFeedHasMore = true;
        tmdbFeedItems = [];
        const searchInput = document.getElementById('tmdbSearchInput');
        if (searchInput) searchInput.value = '';
        container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><p>加载中...</p></div>';
    }

    if (!tmdbFeedHasMore && !reset) {
        return;
    }

    tmdbFeedLoading = true;
    if (loadMoreBtn) {
        loadMoreBtn.disabled = true;
        loadMoreBtn.style.display = 'none';
    }

    try {
        const res = await authFetch(`/api/tmdb/feed?feed=${encodeURIComponent(feed)}&page=${tmdbFeedPage}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status !== 'success') {
            const msg = data.detail || data.message || '加载失败';
            container.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>${escapeHtml(msg)}</p></div>`;
            return;
        }

        const items = Array.isArray(data.items) ? data.items : [];
        tmdbFeedItems = tmdbFeedItems.concat(items);
        tmdbFeedHasMore = !!data.pagination?.has_more;
        if (tmdbFeedHasMore) {
            tmdbFeedPage += 1;
        }

        try {
            const ids = items.map(x => x?.id).filter(Boolean);
            if (ids.length) {
                const resp = await authFetch('/api/emby/in_library', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tmdb_ids: ids })
                });
                const mapData = await resp.json().catch(() => ({}));
                if (resp.ok && mapData.status === 'success') {
                    const map = {};
                    for (const r of (mapData.results || [])) {
                        map[String(r.tmdb_id)] = !!r.in_library;
                    }
                    tmdbFeedItems = tmdbFeedItems.map(item => {
                        const idStr = String(item?.id || '');
                        if (idStr && map.hasOwnProperty(idStr)) {
                            return { ...item, in_library: map[idStr] };
                        }
                        return item;
                    });
                }
            }
        } catch (_) {}

        filterTmdbFeed();

        if (loadMoreBtn) {
            loadMoreBtn.style.display = tmdbFeedHasMore ? 'inline-flex' : 'none';
        }
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>${escapeHtml(error.message || '加载失败')}</p></div>`;
    } finally {
        tmdbFeedLoading = false;
        if (loadMoreBtn) {
            loadMoreBtn.disabled = false;
        }
    }
}
