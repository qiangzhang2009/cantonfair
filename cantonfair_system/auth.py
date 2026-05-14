# ============================================================
# CantonFair Pro — 认证与权限管理
# 支持: 用户密码认证 + Session 管理
# ============================================================
import os
import re
import hashlib
import secrets
import time
import json
from typing import Optional
from functools import wraps

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


# ---------- 用户配置 ----------
def get_auth_config() -> dict:
    """从环境变量读取用户配置"""
    secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))
    users_raw = os.environ.get('AUTH_USERS', 'admin:cantonfair2026')
    # 格式: user:pass_hash,user2:pass_hash2
    users = {}
    for entry in users_raw.split(','):
        if ':' in entry:
            username, password_hash = entry.split(':', 1)
            users[username.strip()] = password_hash.strip()
    return {'secret_key': secret_key, 'users': users}


def _get_secret_key() -> str:
    config = get_auth_config()
    return config['secret_key']


def _verify_password(username: str, password: str) -> bool:
    """验证用户名密码"""
    config = get_auth_config()
    users = config['users']

    if username not in users:
        return False

    stored_hash = users[username]

    # bcrypt 格式: $2b$12$...
    if stored_hash.startswith('$2'):
        if HAS_BCRYPT:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
            except Exception:
                return False
        else:
            return password == stored_hash  # 回退到明文（仅开发模式）

    # SHA256 格式
    if len(stored_hash) == 64:
        h = hashlib.sha256(password.encode()).hexdigest()
        return h == stored_hash

    # 明文（仅本地开发）
    return password == stored_hash


def _make_session_token(username: str) -> str:
    """生成 session token"""
    key = _get_secret_key()
    raw = f"{username}:{key}:{time.time()}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    return f"{username}:{token}"


def _verify_session_token(token: str) -> Optional[str]:
    """验证 session token，返回用户名"""
    if not token or ':' not in token:
        return None
    parts = token.split(':', 1)
    if len(parts) != 2:
        return None
    username, hash_part = parts
    # 简单验证（实际生产建议用 JWT 或 proper sessions）
    config = get_auth_config()
    if username not in config['users']:
        return None
    return username


# ---------- Streamlit 认证装饰器/工具 ----------
SESSION_KEY = 'cantonfair_auth'
TOKEN_KEY = 'cf_session_token'
USER_KEY = 'cf_logged_in_user'


def is_authenticated() -> bool:
    """检查当前是否已登录"""
    if not HAS_STREAMLIT:
        return True
    return st.session_state.get(USER_KEY, None) is not None


def get_current_user() -> Optional[str]:
    """获取当前登录用户"""
    if not HAS_STREAMLIT:
        return os.environ.get('DEFAULT_USER', 'admin')
    return st.session_state.get(USER_KEY, None)


def login_user(username: str, password: str) -> bool:
    """登录用户"""
    if not HAS_STREAMLIT:
        return True
    if _verify_password(username, password):
        st.session_state[USER_KEY] = username
        token = _make_session_token(username)
        st.session_state[TOKEN_KEY] = token
        return True
    return False


def logout_user():
    """登出当前用户"""
    if not HAS_STREAMLIT:
        return
    st.session_state[USER_KEY] = None
    st.session_state[TOKEN_KEY] = None


def require_auth(func):
    """Streamlit 页面认证装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            show_login_page()
            return None
        return func(*args, **kwargs)
    return wrapper


# ---------- 登录页面 ----------
def show_login_page():
    """渲染登录页面"""
    if not HAS_STREAMLIT:
        return

    st.markdown("""
    <style>
        body { background: #0F172A; }
        .stApp { background: #0F172A; }
        .login-container {
            max-width: 400px;
            margin: 80px auto;
            padding: 40px;
            background: #1E293B;
            border-radius: 20px;
            border: 1px solid #334155;
            text-align: center;
        }
        .login-title { font-size: 28px; font-weight: 800; color: #F1F5F9; margin-bottom: 8px; }
        .login-sub { color: #64748B; font-size: 14px; margin-bottom: 32px; }
        .stTextInput > div > div > input {
            background: #0F172A !important;
            border: 1px solid #334155 !important;
            color: #F1F5F9 !important;
            border-radius: 8px !important;
        }
        .stTextInput > label { color: #94A3B8 !important; }
        .stButton > button {
            width: 100%;
            background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
        }
        .stButton > button:hover {
            box-shadow: 0 6px 20px rgba(37,99,235,0.5) !important;
        }
        .login-error { color: #EF4444; font-size: 14px; margin-top: 12px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; margin-bottom:32px;">
        <div style="font-size:48px;">🏭</div>
        <div class="login-title">CantonFair Pro</div>
        <div class="login-sub">智能外贸撮合系统 · 请登录</div>
    </div>
    """)

    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("用户名", placeholder="请输入用户名", label_visibility="collapsed")
        password = st.text_input("密码", type="password", placeholder="请输入密码", label_visibility="collapsed")
        submitted = st.form_submit_button("登 录", use_container_width=True)

        if submitted:
            if login_user(username, password):
                st.rerun()
            else:
                st.markdown('<div class="login-error">用户名或密码错误</div>', unsafe_allow_html=True)


# ---------- 认证状态注入（需要放在每个受保护页面的最前面）----------
def inject_auth_check():
    """
    在受保护页面的 st.set_page_config 之后调用
    如果未登录则渲染登录页面并停止执行
    """
    if not is_authenticated():
        show_login_page()
        st.stop()


def render_auth_sidebar():
    """在侧边栏渲染用户信息"""
    if not HAS_STREAMLIT:
        return
    user = get_current_user()
    if user:
        st.sidebar.markdown("""
        <div style="text-align:center; padding:8px 0; border-top:1px solid #334155; margin-top:16px;">
            <div style="font-size:12px; color:#64748B;">当前用户</div>
            <div style="font-size:14px; font-weight:600; color:#F1F5F9; margin-top:4px;">""" + user + """</div>
        </div>
        """, unsafe_allow_html=True)
        if st.sidebar.button("退出登录", use_container_width=True):
            logout_user()
            st.rerun()


# ---------- 密码生成工具 ----------
def generate_password_hash(password: str) -> str:
    """生成 bcrypt 密码哈希（用于 AUTH_USERS 配置）"""
    if HAS_BCRYPT:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode()
    return hashlib.sha256(password.encode()).hexdigest()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='生成密码哈希')
    parser.add_argument('password', help='要哈希的密码')
    args = parser.parse_args()
    h = generate_password_hash(args.password)
    print(f"密码哈希: {h}")
    print(f"\n添加到 .env 的 AUTH_USERS:")
    print(f"AUTH_USERS=admin:{h}")
