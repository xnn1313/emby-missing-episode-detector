"""
Emby 缺集检测系统 - 卡片流 UI 组件
参考 moviepilot 风格设计
"""

def get_card_style_css():
    """返回卡片流样式"""
    return """
<style>
    /* 卡片流容器 */
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 20px;
        padding: 20px 0;
    }
    
    /* 单个卡片 */
    .series-card {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .series-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    }
    
    /* 卡片封面 */
    .card-poster {
        position: relative;
        width: 100%;
        padding-top: 150%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        overflow: hidden;
    }
    
    .card-poster img {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .card-poster .placeholder {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: white;
        font-size: 48px;
    }
    
    /* 卡片状态标签 */
    .card-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        color: white;
    }
    
    .badge-ongoing {
        background: linear-gradient(135deg, #11998e, #38ef7d);
    }
    
    .badge-ended {
        background: linear-gradient(135deg, #667eea, #764ba2);
    }
    
    .badge-missing {
        background: linear-gradient(135deg, #eb3349, #f45c43);
    }
    
    /* 卡片内容 */
    .card-content {
        padding: 16px;
    }
    
    .card-title {
        font-size: 16px;
        font-weight: 600;
        color: #333;
        margin-bottom: 8px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .card-year {
        font-size: 14px;
        color: #999;
        margin-bottom: 12px;
    }
    
    /* 缺集统计 */
    .card-stats {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        background: #f8f9fa;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    
    .stat-item {
        text-align: center;
    }
    
    .stat-value {
        font-size: 20px;
        font-weight: 700;
        color: #eb3349;
    }
    
    .stat-label {
        font-size: 12px;
        color: #666;
        margin-top: 2px;
    }
    
    /* 卡片操作 */
    .card-actions {
        display: flex;
        gap: 8px;
    }
    
    .card-btn {
        flex: 1;
        padding: 8px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .btn-primary:hover {
        opacity: 0.9;
    }
    
    .btn-secondary {
        background: #f0f0f0;
        color: #666;
    }
    
    .btn-secondary:hover {
        background: #e0e0e0;
    }
    
    /* 展开详情 */
    .card-detail {
        display: none;
        padding: 16px;
        border-top: 1px solid #f0f0f0;
    }
    
    .card-detail.expanded {
        display: block;
    }
    
    .season-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .season-item {
        padding: 8px 0;
        border-bottom: 1px solid #f0f0f0;
    }
    
    .season-item:last-child {
        border-bottom: none;
    }
    
    .season-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    
    .season-title {
        font-weight: 600;
        color: #333;
    }
    
    .missing-episodes {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    
    .episode-tag {
        background: #fff3f3;
        color: #eb3349;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
    }
    
    /* 空状态 */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #999;
    }
    
    .empty-state-icon {
        font-size: 64px;
        margin-bottom: 20px;
    }
    
    .empty-state-title {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 10px;
        color: #666;
    }
    
    .empty-state-desc {
        font-size: 14px;
        line-height: 1.6;
    }
    
    /* 筛选栏 */
    .filter-bar {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }
    
    .filter-select {
        padding: 10px 16px;
        border: 1px solid #ddd;
        border-radius: 8px;
        font-size: 14px;
        background: white;
        cursor: pointer;
    }
    
    .filter-select:focus {
        outline: none;
        border-color: #667eea;
    }
    
    /* 加载状态 */
    .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 60px;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
</style>
"""


def get_card_html(series_list):
    """生成卡片流 HTML"""
    if not series_list:
        return get_empty_state_html()
    
    cards_html = []
    for series in series_list:
        card = create_series_card(series)
        cards_html.append(card)
    
    return f"""
    <div class="card-grid">
        {''.join(cards_html)}
    </div>
    """


def create_series_card(series):
    """创建单个剧集卡片"""
    series_name = series.get('series_name', '未知剧集')
    series_year = series.get('year', '未知年份')
    poster_url = series.get('poster', '')
    status = series.get('status', 'ongoing')  # ongoing, ended
    missing_count = series.get('missing_count', 0)
    total_seasons = series.get('total_seasons', 0)
    tmdb_id = series.get('tmdb_id', '')
    seasons = series.get('seasons', [])
    
    # 状态标签
    badge_class = "badge-ongoing" if status == "ongoing" else "badge-ended"
    badge_text = "连载" if status == "ongoing" else "完结"
    
    # 封面图
    if poster_url:
        poster_html = f'<img src="{poster_url}" alt="{series_name}" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">'
    else:
        poster_html = ''
    
    poster_html += f'<div class="placeholder" style="display: {"none" if poster_url else "block"}">📺</div>'
    
    # 缺集统计
    stats_html = f"""
    <div class="card-stats">
        <div class="stat-item">
            <div class="stat-value">{missing_count}</div>
            <div class="stat-label">缺失集数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{total_seasons}</div>
            <div class="stat-label">总季数</div>
        </div>
    </div>
    """
    
    # 季详情
    seasons_html = []
    for season in seasons:
        season_num = season.get('season_number', 0)
        missing_eps = season.get('missing_episodes', [])
        if missing_eps:
            eps_tags = ''.join([f'<span class="episode-tag">E{ep:02d}</span>' for ep in missing_eps[:10]])
            if len(missing_eps) > 10:
                eps_tags += f'<span class="episode-tag">+{len(missing_eps)-10}更多</span>'
            
            seasons_html.append(f"""
            <li class="season-item">
                <div class="season-header">
                    <span class="season-title">第{season_num}季</span>
                    <span style="color: #eb3349; font-size: 12px;">缺失 {len(missing_eps)} 集</span>
                </div>
                <div class="missing-episodes">{eps_tags}</div>
            </li>
            """)
    
    seasons_list_html = f'<ul class="season-list">{"".join(seasons_html)}</ul>' if seasons_html else '<p style="color: #999; font-size: 14px;">暂无缺集详情</p>'
    
    return f"""
    <div class="series-card" onclick="toggleCard(this)">
        <div class="card-poster">
            {poster_html}
            <span class="card-badge {badge_class}">{badge_text}</span>
        </div>
        <div class="card-content">
            <div class="card-title">{series_name}</div>
            <div class="card-year">{series_year}</div>
            {stats_html}
            <div class="card-actions">
                <button class="card-btn btn-primary" onclick="event.stopPropagation(); viewDetail('{tmdb_id}')">查看详情</button>
                <button class="card-btn btn-secondary" onclick="event.stopPropagation(); toggleCard(this.closest('.series-card'))">展开</button>
            </div>
        </div>
        <div class="card-detail">
            <h4 style="margin-bottom: 12px; color: #333;">缺集详情</h4>
            {seasons_list_html}
        </div>
    </div>
    """


def get_empty_state_html():
    """生成空状态 HTML"""
    return """
    <div class="empty-state">
        <div class="empty-state-icon">🎉</div>
        <div class="empty-state-title">太棒了！</div>
        <div class="empty-state-desc">
            所有剧集都是完整的<br>
            没有发现任何缺集
        </div>
    </div>
    """


def get_loading_html():
    """生成加载状态 HTML"""
    return """
    <div class="loading-spinner">
        <div class="spinner"></div>
    </div>
    """


def get_filter_bar_html(libraries, status_options, sort_options):
    """生成筛选栏 HTML"""
    lib_options = ''.join([f'<option value="{lib.get("id", "")}">{lib.get("name", "全部")}</option>' for lib in libraries])
    status_opts = ''.join([f'<option value="{opt.get("value", "")}">{opt.get("label", "全部")}</option>' for opt in status_options])
    sort_opts = ''.join([f'<option value="{opt.get("value", "")}">{opt.get("label", "默认排序")}</option>' for opt in sort_options])
    
    return f"""
    <div class="filter-bar">
        <select class="filter-select" id="filter-library">
            <option value="">全部媒体库</option>
            {lib_options}
        </select>
        <select class="filter-select" id="filter-status">
            <option value="">全部状态</option>
            {status_opts}
        </select>
        <select class="filter-select" id="filter-sort">
            <option value="">默认排序</option>
            {sort_opts}
        </select>
    </div>
    """
