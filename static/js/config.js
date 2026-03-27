// ========== 配置页面 ==========

function updateWeComCallbackUrl() {
    const callbackInput = document.getElementById('wecomCallbackUrl');
    if (!callbackInput) return;
    callbackInput.value = `${window.location.origin}/api/wecom/callback`;

    const searchCallbackInput = document.getElementById('wecomSearchCallbackUrl');
    if (searchCallbackInput) {
        searchCallbackInput.value = `${window.location.origin}/api/wecom/search/callback`;
    }
}

function showConfigStatus(elId, type, html) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.style.display = 'block';
    el.style.background = type === 'success' ? '#1a3a1a' : type === 'loading' ? '#1a1a2e' : '#3a1a1a';
    el.innerHTML = html;
}

async function loadConfig() {
    try {
        updateWeComCallbackUrl();

        const response = await authFetch('/api/config');
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('embyHost').value = data.config.emby?.host || '';
            document.getElementById('embyApiKey').value = data.config.emby?.api_key || '';
            document.getElementById('tmdbApiKey').value = data.config.tmdb?.api_key || '';
            document.getElementById('mpHost').value = data.config.moviepilot?.host || '';
            document.getElementById('mpUsername').value = data.config.moviepilot?.username || 'admin';
            document.getElementById('mpPassword').value = data.config.moviepilot?.password || '';
        }

        // 加载 HDHive 配置
        const hdhiveRes = await authFetch('/api/hdhive/config');
        const hdhiveData = await hdhiveRes.json();
        if (hdhiveData.status === 'success') {
            const hc = hdhiveData.config;
            document.getElementById('hdhiveApiKey').value = hc.api_key || '';
            document.getElementById('hdhiveBaseUrl').value = hc.base_url || 'https://hdhive.com/api/open';
            document.getElementById('hdhiveEnabled').checked = hc.enabled || false;
            document.getElementById('hdhiveProxyEnabled').checked = hc.proxy?.enabled || false;
            document.getElementById('hdhiveProxyHost').value = hc.proxy?.host || '';
            document.getElementById('hdhiveProxyPort').value = hc.proxy?.port || '';
            document.getElementById('hdhiveProxyUser').value = hc.proxy?.username || '';
            document.getElementById('hdhiveProxyPass').value = '';
            document.getElementById('hdhiveMaxPoints').value = hc.settings?.max_points_per_unlock || 50;
            const gpEnabled = document.getElementById('globalProxyEnabled');
            const gpHost = document.getElementById('globalProxyHost');
            const gpPort = document.getElementById('globalProxyPort');
            const gpUser = document.getElementById('globalProxyUser');
            if (gpEnabled) gpEnabled.checked = hc.proxy?.enabled || false;
            if (gpHost) gpHost.value = hc.proxy?.host || '';
            if (gpPort) gpPort.value = hc.proxy?.port || '';
            if (gpUser) gpUser.value = hc.proxy?.username || '';
        }

        const wecomRes = await authFetch('/api/wecom/config');
        const wecomData = await wecomRes.json();
        if (wecomData.status === 'success') {
            const wc = wecomData.config;
            document.getElementById('wecomEnabled').checked = wc.enabled || false;
            document.getElementById('wecomCorpId').value = wc.corp_id || '';
            document.getElementById('wecomAgentId').value = wc.agent_id || '';
            document.getElementById('wecomCorpSecret').value = wc.corp_secret || '';
            document.getElementById('wecomToken').value = wc.token || '';
            document.getElementById('wecomEncodingAesKey').value = wc.encoding_aes_key || '';
            document.getElementById('wecomBaseUrl').value = wc.base_url || 'https://qyapi.weixin.qq.com/cgi-bin';
        }

        const wecomSearchRes = await authFetch('/api/wecom/search/config');
        const wecomSearchData = await wecomSearchRes.json();
        if (wecomSearchData.status === 'success') {
            const ws = wecomSearchData.config;
            document.getElementById('wecomSearchEnabled').checked = ws.enabled || false;
            document.getElementById('wecomSearchCorpId').value = ws.corp_id || '';
            document.getElementById('wecomSearchAgentId').value = ws.agent_id || '';
            document.getElementById('wecomSearchCorpSecret').value = ws.corp_secret || '';
            document.getElementById('wecomSearchToken').value = ws.token || '';
            document.getElementById('wecomSearchEncodingAesKey').value = ws.encoding_aes_key || '';
            document.getElementById('wecomSearchPansouUrl').value = ws.pansou_url || 'http://47.108.129.71:57081';
        }

        const symRes = await authFetch('/api/symedia/config');
        const symData = await symRes.json();
        if (symData.status === 'success') {
            const sc = symData.config;
            document.getElementById('symediaEnabled').checked = sc.enabled || false;
            document.getElementById('symediaHost').value = sc.host || '';
            document.getElementById('symediaToken').value = sc.token || 'symedia';
            document.getElementById('symediaParentId').value = sc.parent_id || '0';
        } else {
            document.getElementById('symediaEnabled').checked = false;
            document.getElementById('symediaHost').value = '';
            document.getElementById('symediaToken').value = 'symedia';
            document.getElementById('symediaParentId').value = '0';
        }

        const meRes = await authFetch('/api/auth/me');
        if (meRes.ok) {
            const meData = await meRes.json();
            window.currentAdminName = meData?.user?.username || 'admin';
            const userInput = document.getElementById('adminUsername');
            if (userInput) userInput.value = window.currentAdminName;
        }

        showConfigTab('emby');
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

window.saveConfig = async function(e) {
    e.preventDefault();

    const embyHost = document.getElementById('embyHost').value.trim();
    const embyApiKey = document.getElementById('embyApiKey').value.trim();

    if (!embyHost || !embyApiKey) {
        alert('Emby 配置不能为空！\n请填写服务器地址和 API 密钥');
        return;
    }

    const config = {
        emby: { host: embyHost, api_key: embyApiKey },
        moviepilot: {
            host: document.getElementById('mpHost').value.trim(),
            username: document.getElementById('mpUsername').value.trim(),
            password: document.getElementById('mpPassword').value.trim(),
            enabled: true,
            auto_download: true
        },
        libraries: { enabled: false, selected_ids: [] },
        tmdb: {
            enabled: !!document.getElementById('tmdbApiKey').value.trim(),
            api_key: document.getElementById('tmdbApiKey').value.trim()
        },
        detection: { interval_minutes: 60, auto_start: true }
    };

    try {
        const response = await authFetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        // 保存 HDHive 配置
        const hdhiveConfig = {
            api_key: document.getElementById('hdhiveApiKey').value.trim(),
            base_url: document.getElementById('hdhiveBaseUrl').value.trim() || 'https://hdhive.com/api/open',
            enabled: document.getElementById('hdhiveEnabled').checked,
            proxy: {
                enabled: document.getElementById('globalProxyEnabled').checked,
                host: document.getElementById('globalProxyHost').value.trim(),
                port: parseInt(document.getElementById('globalProxyPort').value) || 0,
                username: document.getElementById('globalProxyUser').value.trim(),
                password: document.getElementById('hdhiveProxyPass').value.trim()
            },
            settings: {
                max_points_per_unlock: parseInt(document.getElementById('hdhiveMaxPoints').value) || 50,
                prefer_115: true,
                auto_unlock: false
            }
        };

        await authFetch('/api/hdhive/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(hdhiveConfig)
        });

        const wecomConfig = {
            enabled: document.getElementById('wecomEnabled').checked,
            corp_id: document.getElementById('wecomCorpId').value.trim(),
            agent_id: parseInt(document.getElementById('wecomAgentId').value) || 0,
            corp_secret: document.getElementById('wecomCorpSecret').value.trim(),
            token: document.getElementById('wecomToken').value.trim(),
            encoding_aes_key: document.getElementById('wecomEncodingAesKey').value.trim(),
            base_url: document.getElementById('wecomBaseUrl').value.trim() || 'https://qyapi.weixin.qq.com/cgi-bin'
        };

        const wecomResp = await authFetch('/api/wecom/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(wecomConfig)
        });
        const wecomData = await wecomResp.json();

        const wecomSearchConfig = {
            enabled: document.getElementById('wecomSearchEnabled').checked,
            corp_id: document.getElementById('wecomSearchCorpId').value.trim(),
            agent_id: parseInt(document.getElementById('wecomSearchAgentId').value) || 0,
            corp_secret: document.getElementById('wecomSearchCorpSecret').value.trim(),
            token: document.getElementById('wecomSearchToken').value.trim(),
            encoding_aes_key: document.getElementById('wecomSearchEncodingAesKey').value.trim(),
            pansou_url: document.getElementById('wecomSearchPansouUrl').value.trim() || 'http://47.108.129.71:57081',
        };
        await authFetch('/api/wecom/search/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(wecomSearchConfig)
        });

        const symediaConfig = {
            enabled: document.getElementById('symediaEnabled').checked,
            host: document.getElementById('symediaHost').value.trim(),
            token: document.getElementById('symediaToken').value.trim() || 'symedia',
            parent_id: document.getElementById('symediaParentId').value.trim() || '0'
        };
        const symResp = await authFetch('/api/symedia/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(symediaConfig)
        });
        const symData = await symResp.json();

        const adminPassword = document.getElementById('adminPassword').value.trim();
        const adminUsername = document.getElementById('adminUsername').value.trim();
        const willChangeName = adminUsername && window.currentAdminName && adminUsername !== window.currentAdminName;
        if (adminPassword || willChangeName) {
            const payload = {};
            if (adminPassword) payload['new_password'] = adminPassword;
            if (willChangeName) payload['new_username'] = adminUsername;
            const accResp = await authFetch('/api/auth/account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!accResp.ok) {
                const err = await accResp.json().catch(() => ({}));
                alert('管理员账号修改失败：' + (err.detail || err.message || '未知错误'));
                return;
            }
            const accData = await accResp.json().catch(() => ({}));
            if (accData.require_relogin) {
                alert('管理员账号已更新，请重新登录');
                logout();
                return;
            }
        }

        if (data.status === 'success' || response.ok) {
            const wecomLine = wecomData?.test_result ? ('\n企业微信: ' + wecomData.test_result) : '';
            alert('✅ 配置已保存！\n\nEmby: ' + embyHost + '\nMoviePilot: ' + config.moviepilot.host + wecomLine);
        } else {
            alert('保存失败：' + (data.detail || data.message || '未知错误'));
        }
    } catch (error) {
        alert('保存失败：' + error.message);
    }
}

window.showConfigTab = function(name) {
    const tabs = ['emby', 'mp', 'hdhive', 'wecom', 'wecom-search', 'symedia', 'global'];
    tabs.forEach(t => {
        const sec = document.getElementById('cfgSection-' + t);
        const btn = document.getElementById('cfgTab-' + t);
        if (sec) sec.classList.toggle('active', t === name);
        if (btn) btn.classList.toggle('active', t === name);
    });
}

window.testHdhiveConnection = async function() {
    showConfigStatus('hdhiveStatus', 'loading', '<i class="fas fa-spinner fa-spin"></i> 测试连接中...');

    try {
        const response = await authFetch('/api/hdhive/status');
        const data = await response.json();

        if (data.status === 'success') {
            showConfigStatus('hdhiveStatus', 'success', `
                <p style="color: #4ade80;"><i class="fas fa-check-circle"></i> 连接成功！</p>
                <p>用户: ${data.user?.nickname || '未知'}</p>
                <p>积分: ${data.user?.points || 0}</p>
                <p>VIP: ${data.user?.is_vip ? '是' : '否'}</p>
            `);
        } else {
            showConfigStatus('hdhiveStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> ${data.message || '连接失败'}</p>`);
        }
    } catch (error) {
        showConfigStatus('hdhiveStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> 连接失败: ${error.message}</p>`);
    }
}

window.testWeComConnection = async function() {
    showConfigStatus('wecomStatus', 'loading', '<i class="fas fa-spinner fa-spin"></i> 测试企业微信连接中...');

    try {
        const response = await authFetch('/api/wecom/status');
        const data = await response.json();

        if (data.status === 'success') {
            const callbackReady = data.callback_ready ? '已配置' : '未配置';
            const sendReady = data.send_ready ? '已配置' : '未配置';
            showConfigStatus('wecomStatus', 'success', `
                <p style="color: #4ade80;"><i class="fas fa-check-circle"></i> ${data.message || '企业微信可用'}</p>
                <p>回调验签: ${callbackReady}</p>
                <p>主动发送: ${sendReady}</p>
                <p>回调地址: ${document.getElementById('wecomCallbackUrl').value}</p>
            `);
        } else {
            showConfigStatus('wecomStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> ${data.message || '连接失败'}</p>`);
        }
    } catch (error) {
        showConfigStatus('wecomStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> 连接失败: ${error.message}</p>`);
    }
}

window.testWeComSearchConnection = async function() {
    showConfigStatus('wecomSearchStatus', 'loading', '<i class="fas fa-spinner fa-spin"></i> 测试连接中...');

    try {
        const response = await authFetch('/api/wecom/search/status');
        const data = await response.json();

        if (data.status === 'success') {
            const callbackReady = data.callback_ready ? '已配置' : '未配置';
            const sendReady = data.send_ready ? '已配置' : '未配置';
            showConfigStatus('wecomSearchStatus', 'success', `
                <p style="color: #4ade80;"><i class="fas fa-check-circle"></i> ${data.message || '连接正常'}</p>
                <p>回调验签: ${callbackReady}</p>
                <p>主动发送: ${sendReady}</p>
                <p>回调地址: ${document.getElementById('wecomSearchCallbackUrl').value}</p>
            `);
        } else {
            showConfigStatus('wecomSearchStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> ${data.message || '连接失败'}</p>`);
        }
    } catch (error) {
        showConfigStatus('wecomSearchStatus', 'error', `<p style="color: #f87171;"><i class="fas fa-times-circle"></i> 连接失败: ${error.message}</p>`);
    }
}
