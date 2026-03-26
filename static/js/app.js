// ========== 应用路由与全局 UI ==========

window.showPage = function(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById('page-' + pageId).classList.add('active');

    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.getAttribute('onclick') && item.getAttribute('onclick').includes("showPage('" + pageId + "')")) {
            item.classList.add('active');
        }
    });

    // 移动端关闭侧边栏
    document.getElementById('sidebar').classList.remove('open');

    // 加载对应数据
    if (pageId === 'dashboard') loadDashboard();
    if (pageId === 'download') loadDownloads();
    if (pageId === 'config') loadConfig();
    if (pageId === 'history') loadHistory();
    if (pageId === 'tmdb') loadTmdbFeed(true);
    if (pageId === 'hdhive') loadHdhiveSearch();

    const nextHash = pageId ? `#/${pageId}` : '#/dashboard';
    if (window.location.hash !== nextHash) {
        window.location.hash = nextHash;
    }
}

window.toggleSidebar = function() {
    document.getElementById('sidebar').classList.toggle('open');
}

window.toggleTheme = function() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => {
        switch (ch) {
            case '&': return '&amp;';
            case '<': return '&lt;';
            case '>': return '&gt;';
            case '"': return '&quot;';
            case "'": return '&#39;';
            default: return ch;
        }
    });
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    updateWeComCallbackUrl();

    // 加载主题
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
    }

    const loginPwd = document.getElementById('loginPassword');
    if (loginPwd) {
        loginPwd.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitLogin();
            }
        });
    }

    async function route() {
        const hash = window.location.hash || '';
        if (hash === LOGIN_HASH) {
            showLoginPage();
            return;
        }

        const ok = await validateToken();
        if (!ok) {
            location.hash = LOGIN_HASH;
            showLoginPage();
            return;
        }

        showAppShell();

        const page = hash.startsWith('#/') ? hash.slice(2) : '';
        const targetPage = page && page !== 'login' ? page : 'dashboard';
        const targetEl = document.getElementById('page-' + targetPage);
        const alreadyActive = targetEl && targetEl.classList.contains('active');
        if (!alreadyActive) {
            showPage(targetPage);
        }
    }

    window.addEventListener('hashchange', () => {
        route();
    });

    route();

    const tmdbGrid = document.getElementById('tmdbGrid');
    if (tmdbGrid) {
        tmdbGrid.addEventListener('click', function(e) {
            const btn = e.target.closest('.tmdb-hdhive-btn');
            if (!btn) return;
            e.preventDefault();
            const tmdbId = (btn.dataset.tmdbId || '').trim();
            const seriesName = btn.dataset.seriesName || '';
            if (!tmdbId) return;
            searchHdhive('', seriesName || `TMDB ${tmdbId}`, tmdbId, null);
        });
    }

    // 事件委托：处理下载按钮点击
    document.getElementById('seriesGrid').addEventListener('click', function(e) {
        const downloadBtn = e.target.closest('.download-btn');
        if (downloadBtn) {
            e.preventDefault();
            const seriesId = downloadBtn.dataset.seriesId;
            const seriesName = downloadBtn.dataset.seriesName;
            const season = parseInt(downloadBtn.dataset.season) || 1;
            pushDownload(seriesId, seriesName, season, downloadBtn);
            return;
        }

        const hdhiveBtn = e.target.closest('.hdhive-btn');
        if (hdhiveBtn) {
            e.preventDefault();
            const seriesId = hdhiveBtn.dataset.seriesId;
            const seriesName = hdhiveBtn.dataset.seriesName;
            const season = hdhiveBtn.dataset.season || 1;
            const tmdbId = hdhiveBtn.dataset.tmdbId;
            searchHdhive(seriesId, seriesName, tmdbId, season);
        }
    });
});
