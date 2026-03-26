// ========== HDHive 搜索页面 ==========

function setHdhiveSearchStatus(type, html) {
    const el = document.getElementById('hdhiveSearchStatus');
    if (!el) return;
    el.style.display = 'block';
    el.style.background = type === 'success' ? '#1a3a1a' : type === 'loading' ? '#1a1a2e' : '#3a1a1a';
    el.innerHTML = html;
}

async function loadHdhiveSearch() {
    await ensureAuthenticated(false);
}

window.clearHdhiveSearch = function() {
    const keyword = document.getElementById('hdhiveKeyword');
    const tmdbId = document.getElementById('hdhiveTmdbId');
    const season = document.getElementById('hdhiveSeason');
    const status = document.getElementById('hdhiveSearchStatus');
    const result = document.getElementById('hdhiveSearchResult');

    if (keyword) keyword.value = '';
    if (tmdbId) tmdbId.value = '';
    if (season) season.value = '';
    if (status) status.style.display = 'none';
    if (result) result.innerHTML = '';
}

function buildPanBadge(panType, title) {
    const is115 = panType === '115' || (title && title.toLowerCase().includes('115'));
    const isAli = panType === 'ali' || panType === 'aliyun' || (title && title.toLowerCase().includes('阿里'));
    const isQuark = panType === 'quark' || (title && title.toLowerCase().includes('夸克'));
    const isBaidu = panType === 'baidu' || (title && title.toLowerCase().includes('百度'));

    if (is115) return '<span style="background:#667eea;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;">115</span>';
    if (isAli) return '<span style="background:#00c853;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;color:#fff;">阿里云盘</span>';
    if (isQuark) return '<span style="background:#00d9ff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;color:#000;">夸克</span>';
    if (isBaidu) return '<span style="background:#29b6f6;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;color:#fff;">百度网盘</span>';
    if (panType) return `<span style="background:#888;padding:2px 8px;border-radius:4px;font-size:12px;">${panType}</span>`;
    return '';
}

function renderHdhiveResources(title, tmdbId, season, resources) {
    const container = document.getElementById('hdhiveSearchResult');
    if (!container) return;

    if (!resources || resources.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-box-open"></i>
                <p>没有找到可用资源</p>
                <div style="color:#888;font-size:13px;margin-top:8px;">TMDB ID: ${tmdbId}${season ? ` / 第${season}季` : ''}</div>
            </div>
        `;
        return;
    }

    let html = `
        <div style="margin-bottom:10px;color:#4ade80;font-weight:600;">
            找到 ${resources.length} 个资源 ${title ? `（${title}）` : ''} ${season ? `- 第${season}季` : ''}
        </div>
    `;

    html += '<div style="max-height:520px;overflow-y:auto;">';
    resources.forEach(r => {
        const panBadge = buildPanBadge(r.pan_type || '', r.title || '');
        html += `<div style="background:#0a0a1a;padding:12px;border-radius:8px;margin-bottom:10px;cursor:pointer;" onclick="unlockHdhiveResource('${r.slug}', '${r.title?.replace(/'/g, "\\'") || '未知'}', ${r.unlock_points}, this)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:10px;">
                <span style="font-weight:bold;color:#fff;">${r.title || '未知标题'}</span>
                ${panBadge}
            </div>
            <div style="display:flex;gap:15px;color:#888;font-size:13px;flex-wrap:wrap;">
                <span><i class="fas fa-hdd"></i> ${r.share_size || '未知'}</span>
                <span><i class="fas fa-video"></i> ${(r.video_resolution || []).join(', ')}</span>
                <span style="color:${r.unlock_points === 0 ? '#4ade80' : '#fbbf24'};"><i class="fas fa-coins"></i> ${r.unlock_points || 0} 积分</span>
            </div>
            ${r.is_unlocked ? '<div style="color:#4ade80;margin-top:5px;font-size:12px;"><i class="fas fa-check"></i> 已解锁</div>' : ''}
        </div>`;
    });
    html += '</div>';

    container.innerHTML = html;
}

async function runHdhiveSearchWithTmdbId(tmdbId, title) {
    const seasonRaw = document.getElementById('hdhiveSeason')?.value;
    const season = seasonRaw ? parseInt(seasonRaw, 10) : null;

    setHdhiveSearchStatus('loading', '<i class="fas fa-spinner fa-spin"></i> 正在搜索 HDHive 资源...');

    const query = new URLSearchParams();
    query.set('tmdb_id', String(tmdbId));
    if (season && Number.isFinite(season)) {
        query.set('season', String(season));
    }

    const res = await authFetch(`/api/hdhive/search?${query.toString()}`);
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
        setHdhiveSearchStatus('error', `<i class="fas fa-times-circle"></i> 查询失败：${data.detail || data.message || '未知错误'}`);
        return;
    }

    setHdhiveSearchStatus('success', `<i class="fas fa-check-circle"></i> 查询成功：TMDB ${tmdbId}${season ? ` / 第${season}季` : ''}`);
    renderHdhiveResources(title || '', String(tmdbId), season, data.resources || []);
}

function renderTmdbCandidates(keyword, candidates) {
    const container = document.getElementById('hdhiveSearchResult');
    if (!container) return;

    const list = Array.isArray(candidates) ? candidates : [];
    if (!list.length) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <p>没有找到"${escapeHtml(keyword)}"的 TMDB 候选</p>
            </div>
        `;
        return;
    }

    let html = `<div style="margin-bottom:10px;color:#4ade80;font-weight:600;">找到 ${list.length} 个候选，请选择：</div>`;
    html += '<div style="max-height:520px;overflow-y:auto;">';

    list.forEach((item) => {
        const id = item?.id;
        const title = item?.name || item?.original_name || '';
        const airDate = item?.first_air_date || '';
        const year = item?.year || (airDate ? String(airDate).slice(0, 4) : '');
        const overview = item?.overview || '';

        html += `
            <div style="background:#0a0a1a;padding:12px;border-radius:8px;margin-bottom:10px;border:1px solid rgba(255,255,255,0.06);">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
                    <div style="min-width:0;">
                        <div style="font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                            ${escapeHtml(title || keyword)}
                        </div>
                        <div style="color:#888;font-size:13px;margin-top:4px;">
                            ${year ? `${escapeHtml(year)} ` : ''}${airDate ? `(${escapeHtml(airDate)}) ` : ''}TMDB: ${escapeHtml(id)}
                        </div>
                    </div>
                    <button class="btn btn-primary" style="padding:8px 14px;white-space:nowrap;" onclick="selectTmdbCandidate('${escapeHtml(id)}','${escapeHtml(title || keyword)}')">
                        选择
                    </button>
                </div>
                ${overview ? `<div style="color:#94a3b8;font-size:13px;margin-top:10px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;">${escapeHtml(overview)}</div>` : ''}
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

window.selectTmdbCandidate = async function(tmdbId, title) {
    const cleanedId = String(tmdbId || '').trim();
    if (!cleanedId) {
        alert('TMDB ID 无效');
        return;
    }
    document.getElementById('hdhiveTmdbId').value = cleanedId;
    await runHdhiveSearchWithTmdbId(cleanedId, title || '');
}

window.runHdhiveKeywordSearch = async function() {
    const keyword = (document.getElementById('hdhiveKeyword')?.value || '').trim();
    if (!keyword) {
        alert('请输入剧名关键词');
        return;
    }

    setHdhiveSearchStatus('loading', '<i class="fas fa-spinner fa-spin"></i> 正在查询 TMDB...');
    const tmdbRes = await authFetch(`/api/tmdb/candidates?name=${encodeURIComponent(keyword)}&limit=5`);
    const tmdbData = await tmdbRes.json();
    if (!tmdbRes.ok || tmdbData.status !== 'success') {
        setHdhiveSearchStatus('error', `<i class="fas fa-times-circle"></i> TMDB 查询失败：${tmdbData.message || tmdbData.detail || '未知错误'}`);
        return;
    }

    setHdhiveSearchStatus('success', `<i class="fas fa-check-circle"></i> TMDB 查询成功，请选择候选`);
    renderTmdbCandidates(keyword, tmdbData.candidates || []);
}

window.runHdhiveTmdbSearch = async function() {
    const tmdbId = (document.getElementById('hdhiveTmdbId')?.value || '').trim();
    if (!tmdbId) {
        alert('请输入 TMDB ID');
        return;
    }
    await runHdhiveSearchWithTmdbId(tmdbId, '');
}

// HDHive 弹窗搜索（从仪表盘卡片调用）
async function searchHdhive(seriesId, seriesName, tmdbId, season) {
    const statusDiv = document.createElement('div');
    statusDiv.className = 'modal';
    statusDiv.id = 'hdhiveModal';
    statusDiv.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;z-index:9999;';
    statusDiv.innerHTML = `
        <div class="modal-content" style="background:#1a1a2e;padding:20px;border-radius:12px;max-width:600px;max-height:80vh;overflow-y:auto;position:relative;">
            <button onclick="document.getElementById('hdhiveModal').remove()" style="position:absolute;top:10px;right:10px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button>
            <h3 style="color:#667eea;margin-bottom:15px;"><i class="fas fa-hive"></i> 查询 HDHive 资源</h3>
            <p style="color:#888;">剧集：${seriesName}</p>
            <div id="hdhiveResult" style="margin-top:15px;"><i class="fas fa-spinner fa-spin"></i> 正在搜索...</div>
        </div>
    `;
    document.body.appendChild(statusDiv);

    try {
        let finalTmdbId = tmdbId;

        if (!finalTmdbId && seriesId) {
            document.getElementById('hdhiveResult').innerHTML = `<i class="fas fa-spinner fa-spin"></i> 正在获取 TMDB ID...`;
            const tmdbRes = await fetch(`/api/tmdb/${seriesId}`);
            const tmdbData = await tmdbRes.json();
            finalTmdbId = tmdbData.tmdb_id;
        }

        if (!finalTmdbId) {
            document.getElementById('hdhiveResult').innerHTML = `
                <p style="color:#fbbf24;">⚠️ 无法获取 TMDB ID</p>
                <p style="color:#888;font-size:13px;">该剧可能在 Emby 中未正确刮削元数据</p>
                <button class="btn btn-outline" style="margin-top:10px;width:100%;" onclick="document.getElementById('hdhiveModal').remove()">关闭</button>
            `;
            return;
        }

        document.getElementById('hdhiveResult').innerHTML = `<i class="fas fa-spinner fa-spin"></i> 正在搜索 HDHive 资源... (TMDB: ${finalTmdbId})`;

        const query = new URLSearchParams();
        if (seriesId) query.set('series_id', String(seriesId));
        query.set('tmdb_id', String(finalTmdbId));
        const seasonNum = season ? parseInt(season, 10) : null;
        if (seasonNum && Number.isFinite(seasonNum)) {
            query.set('season', String(seasonNum));
        }
        const searchRes = await authFetch(`/api/hdhive/search?${query.toString()}`);
        const searchData = await searchRes.json();

        if (searchData.status !== 'success' || !searchData.resources?.length) {
            document.getElementById('hdhiveResult').innerHTML = `
                <p style="color:#fbbf24;">📭 HDHive 暂无此剧资源</p>
                <p style="color:#888;font-size:13px;">TMDB ID: ${finalTmdbId}</p>
                <button class="btn btn-outline" style="margin-top:10px;width:100%;" onclick="document.getElementById('hdhiveModal').remove()">关闭</button>
            `;
            return;
        }

        let html = `<p style="color:#4ade80;margin-bottom:10px;">找到 ${searchData.total} 个资源</p>`;
        html += '<div style="max-height:400px;overflow-y:auto;">';

        searchData.resources.forEach(r => {
            const panBadge = buildPanBadge(r.pan_type || '', r.title || '');
            html += `<div style="background:#0a0a1a;padding:12px;border-radius:8px;margin-bottom:10px;cursor:pointer;" onclick="unlockHdhiveResource('${r.slug}', '${r.title?.replace(/'/g, "\\'") || '未知'}', ${r.unlock_points}, this)">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:bold;color:#fff;">${r.title || '未知标题'}</span>
                    ${panBadge}
                </div>
                <div style="display:flex;gap:15px;color:#888;font-size:13px;">
                    <span><i class="fas fa-hdd"></i> ${r.share_size || '未知'}</span>
                    <span><i class="fas fa-video"></i> ${(r.video_resolution || []).join(', ')}</span>
                    <span style="color:${r.unlock_points === 0 ? '#4ade80' : '#fbbf24'};"><i class="fas fa-coins"></i> ${r.unlock_points || 0} 积分</span>
                </div>
                ${r.is_unlocked ? '<div style="color:#4ade80;margin-top:5px;font-size:12px;"><i class="fas fa-check"></i> 已解锁</div>' : ''}
            </div>`;
        });
        html += '</div>';
        html += '<button class="btn btn-outline" style="margin-top:15px;width:100%;" onclick="this.closest(\'.modal\').remove()">关闭</button>';
        document.getElementById('hdhiveResult').innerHTML = html;

    } catch (error) {
        document.getElementById('hdhiveResult').innerHTML = `<p style="color:#f87171;">查询失败: ${error.message}</p>`;
    }
}

function copyAndClose() {
    const modal = document.getElementById('hdhiveModal');
    if (modal) {
        const linkElem = modal.querySelector('a[href]');
        const codeElem = modal.querySelector('span[style*="fbbf24"]');
        const urlText = linkElem ? linkElem.textContent.trim() : '';
        const accessCode = codeElem ? codeElem.textContent.trim() : '';
        const fullText = accessCode ? urlText + ' ' + accessCode : urlText;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullText).then(() => modal.remove());
        } else {
            const textarea = document.createElement('textarea');
            textarea.value = fullText;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try { document.execCommand('copy'); } catch (e) {}
            document.body.removeChild(textarea);
            modal.remove();
        }
    }
}

async function transferSymedia(rawUrl, rawCode) {
    const btn = event && event.target ? event.target.closest('button') : null;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 转存中...';
    }
    try {
        let url = String(rawUrl || '').trim();
        const code = String(rawCode || '').trim();
        if (url && code && !url.includes('password=')) {
            const sep = url.includes('?') ? '&' : '?';
            url = `${url}${sep}password=${encodeURIComponent(code)}`;
        }
        if (!url) {
            alert('未获取到分享链接');
            return;
        }
        const res = await authFetch('/api/symedia/transfer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status !== 'success') {
            const msg = data.detail || data.message || '转存失败';
            alert('转存失败：' + msg);
            return;
        }
        alert('✅ 转存已提交');
    } catch (err) {
        alert('转存失败：' + (err.message || '未知错误'));
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> 转存';
        }
    }
}

async function unlockHdhiveResource(slug, title, points, elem) {
    if (!confirm(`确定要解锁吗？\n\n资源: ${title}\n消耗积分: ${points}`)) {
        return;
    }

    elem.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 解锁中...';

    try {
        const res = await authFetch('/api/hdhive/unlock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug })
        });
        const data = await res.json();

        if (data.status === 'success') {
            const url = data.data?.full_url || data.data?.url || '';
            const code = data.data?.access_code || '';
            elem.innerHTML = `
                <div style="color:#4ade80;">
                    <p><i class="fas fa-check-circle"></i> 解锁成功！</p>
                    <div style="background:#0a0a1a;padding:10px;border-radius:8px;margin-top:10px;word-break:break-all;">
                        <p style="margin-bottom:5px;">链接: <a href="${url}" target="_blank" style="color:#667eea;">${url}</a></p>
                        ${code ? `<p>访问码: <span style="color:#fbbf24;font-weight:bold;">${code}</span></p>` : ''}
                    </div>
                    <div style="display:flex;gap:8px;margin-top:10px;">
                        <button class="btn btn-primary" style="flex:1;" onclick="event.stopPropagation(); copyAndClose()">复制并关闭</button>
                        <button class="btn btn-outline" style="flex:1;" onclick="event.stopPropagation(); transferSymedia('${url}', '${code}')"><i class="fas fa-cloud-upload-alt"></i> 转存</button>
                    </div>
                </div>
            `;
        } else {
            elem.innerHTML = `<p style="color:#f87171;">解锁失败: ${data.message || '未知错误'}</p>`;
        }
    } catch (error) {
        elem.innerHTML = `<p style="color:#f87171;">解锁失败: ${error.message}</p>`;
    }
}
