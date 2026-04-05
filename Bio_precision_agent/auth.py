"""auth.py — BPA 认证模块（极简单色登录页）"""
import hashlib
import streamlit as st

# ⚠️ 安全提示：以下用户字典仅用于本地演示/个人使用。
# 在生产环境中，请使用数据库存储加盐哈希密码，并启用 HTTPS。
_USERS: dict[str, str] = {
    "admin": hashlib.sha256("admin".encode("utf-8")).hexdigest(),
}


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _sanitize_input(text: str) -> str:
    """简单清洗用户输入，防止基础的 XSS 注入到 HTML 中。"""
    return text.replace("<", "&lt;").replace(">", "&gt;").strip()


def check_credentials(username: str, password: str) -> bool:
    return _USERS.get(username) == _hash(password)


_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, .stApp {
  font-family: 'Inter', -apple-system, sans-serif !important;
  background: #0d0d0d !important;
  color: #e8e8e8 !important;
}
header[data-testid="stHeader"], #MainMenu, footer,
[data-testid="stToolbar"], [data-testid="stDecoration"],
.stDeployButton { display: none !important; }

.main .block-container { max-width: 100% !important; padding: 0 !important; }

/* 输入框 */
.stTextInput > div > div > input {
  background: #1a1a1a !important;
  border: 1px solid rgba(255,255,255,0.1) !important;
  border-radius: 8px !important;
  color: #e8e8e8 !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
  padding: 11px 14px !important;
  transition: border-color .2s !important;
  letter-spacing: .01em !important;
}
.stTextInput > div > div > input:focus {
  border-color: rgba(255,255,255,0.3) !important;
  box-shadow: none !important;
  outline: none !important;
}
.stTextInput > div > div > input::placeholder { color: #404040 !important; }
.stTextInput label {
  color: #606060 !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  letter-spacing: .04em !important;
  text-transform: uppercase !important;
}

/* 登录按钮 — 白色底深色字，高级感 */
.stButton > button[data-testid="baseButton-primary"] {
  background: #e8e8e8 !important;
  color: #0d0d0d !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
  padding: 12px 0 !important;
  width: 100% !important;
  letter-spacing: .02em !important;
  transition: background .2s, transform .15s !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: #ffffff !important;
  transform: translateY(-1px) !important;
}
.stButton > button[data-testid="baseButton-primary"]:active {
  transform: translateY(0) !important;
}

/* 错误提示 */
.stAlert {
  background: rgba(255,255,255,.04) !important;
  border: 1px solid rgba(255,255,255,.08) !important;
  border-radius: 8px !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 13px !important;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 2px; }
</style>"""


def show_login_page():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        # Logo 区域 — 纯单色，无渐变
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;padding:88px 0 36px;">
          <div style="
            width: 52px; height: 52px;
            background: #1a1a1a;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
            margin-bottom: 24px;
          ">🧬</div>
          <h1 style="
            font-family:'Inter',sans-serif;
            font-size: 22px;
            font-weight: 600;
            color: #e8e8e8;
            margin: 0;
            letter-spacing: -0.4px;
            text-align: center;
          ">Bio-Precision Agent</h1>
          <p style="
            font-family:'Inter',sans-serif;
            font-size: 13px;
            color: #404040;
            margin: 8px 0 40px;
            letter-spacing: 0.02em;
          ">v4 · 智能实验方案平台</p>
        </div>
        """, unsafe_allow_html=True)

        username = st.text_input("用户名", placeholder="输入用户名", key="login_user")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        password = st.text_input("密码", type="password", placeholder="输入密码", key="login_pass")
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        if st.button("登 录", use_container_width=True, type="primary", key="login_btn"):
            if check_credentials(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = _sanitize_input(username)
                st.rerun()
            else:
                st.error("用户名或密码不正确")

        st.markdown("""
        <p style="
          text-align:center;
          font-family:'Inter',sans-serif;
          font-size:12px;
          color:#2a2a2a;
          margin-top:36px;
          padding-bottom:60px;
        ">仅限授权用户访问</p>
        """, unsafe_allow_html=True)


def require_login():
    if not st.session_state.get("authenticated"):
        show_login_page()
        st.stop()
