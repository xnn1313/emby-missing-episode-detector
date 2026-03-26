// ========== 认证模块 ==========

const AUTH_TOKEN_KEY = 'emby_detector_auth_token';
const LOGIN_HASH = '#/login';
let pendingLoginPromise = null;
let pendingLoginResolve = null;

function getAuthHeaders(extraHeaders = {}) {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) {
        return extraHeaders;
    }
    return {
        ...extraHeaders,
        Authorization: `Bearer ${token}`
    };
}

function showLoginPage(message) {
    const loginPage = document.getElementById('loginPage');
    const appShell = document.getElementById('appShell');
    const errorEl = document.getElementById('loginError');
    if (loginPage) loginPage.style.display = 'flex';
    if (appShell) appShell.style.display = 'none';
    if (errorEl) {
        if (message) {
            errorEl.style.display = 'block';
            errorEl.textContent = String(message);
        } else {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }
    const pwd = document.getElementById('loginPassword');
    if (pwd) {
        pwd.value = '';
        pwd.focus();
    }
}

function showAppShell() {
    const loginPage = document.getElementById('loginPage');
    const appShell = document.getElementById('appShell');
    if (loginPage) loginPage.style.display = 'none';
    if (appShell) appShell.style.display = 'flex';
}

window.clearLoginForm = function() {
    const user = document.getElementById('loginUsername');
    const pwd = document.getElementById('loginPassword');
    const errorEl = document.getElementById('loginError');
    if (user) user.value = 'admin';
    if (pwd) pwd.value = '';
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }
}

function waitForLogin() {
    if (pendingLoginPromise) {
        return pendingLoginPromise;
    }
    pendingLoginPromise = new Promise((resolve) => {
        pendingLoginResolve = resolve;
    });
    return pendingLoginPromise;
}

async function validateToken() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) {
        return false;
    }
    const meResponse = await fetch('/api/auth/me', {
        headers: getAuthHeaders()
    });
    if (meResponse.ok) {
        return true;
    }
    localStorage.removeItem(AUTH_TOKEN_KEY);
    return false;
}

async function ensureAuthenticated(forcePrompt = false) {
    const ok = await validateToken();
    if (ok && !forcePrompt) {
        return true;
    }
    location.hash = LOGIN_HASH;
    showLoginPage('请先登录');
    return await waitForLogin();
}

async function authFetch(url, options = {}) {
    let response = await fetch(url, {
        ...options,
        headers: getAuthHeaders(options.headers || {})
    });

    if (response.status !== 401) {
        return response;
    }

    const authenticated = await ensureAuthenticated(true);
    if (!authenticated) {
        return response;
    }

    return fetch(url, {
        ...options,
        headers: getAuthHeaders(options.headers || {})
    });
}

window.submitLogin = async function() {
    const username = (document.getElementById('loginUsername')?.value || '').trim();
    const password = document.getElementById('loginPassword')?.value ?? '';
    const errorEl = document.getElementById('loginError');
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }

    if (!username || password === '') {
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.textContent = '请输入用户名和密码';
        }
        return;
    }

    try {
        const loginResponse = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!loginResponse.ok) {
            localStorage.removeItem(AUTH_TOKEN_KEY);
            const data = await loginResponse.json().catch(() => ({}));
            const msg = data?.detail || data?.message || '登录失败，请检查用户名和密码';
            if (errorEl) {
                errorEl.style.display = 'block';
                errorEl.textContent = msg;
            }
            return;
        }

        const loginData = await loginResponse.json();
        localStorage.setItem(AUTH_TOKEN_KEY, loginData.access_token);
        showAppShell();
        if (location.hash === LOGIN_HASH) {
            location.hash = '#/dashboard';
        }
        if (pendingLoginResolve) {
            pendingLoginResolve(true);
        }
    } finally {
        pendingLoginPromise = null;
        pendingLoginResolve = null;
    }
}

window.logout = function() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    location.hash = LOGIN_HASH;
    showLoginPage();
}
