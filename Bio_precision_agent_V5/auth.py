from __future__ import annotations

import hashlib
import html

import streamlit as st


USERS: dict[str, str] = {
    "admin": hashlib.sha256("admin".encode("utf-8")).hexdigest(),
}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _clean_text(value: str) -> str:
    return html.escape(value or "", quote=True).strip()


def check_credentials(username: str, password: str) -> bool:
    return USERS.get(username) == _hash_password(password)


LOGIN_CSS = """
<style>
html, body, .stApp {
  background: #0e1117 !important;
  color: #e8eaf0 !important;
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif !important;
}
header[data-testid="stHeader"], #MainMenu, footer,
[data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton {
  display: none !important;
}
.main .block-container {
  max-width: 440px !important;
  padding-top: 86px !important;
}
.stTextInput input {
  background: #171d2a !important;
  border: 1px solid rgba(255,255,255,.10) !important;
  color: #e8eaf0 !important;
  border-radius: 8px !important;
}
.stButton button {
  border-radius: 8px !important;
}
</style>
"""


def show_login_page() -> None:
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:34px">
          <div style="font-size:36px;margin-bottom:12px">Bio-Precision Agent</div>
          <div style="color:#8a95a8;font-size:14px">V5 evidence-grounded biomedical protocol builder</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    username = st.text_input("Username", placeholder="admin", key="login_user")
    password = st.text_input("Password", type="password", placeholder="admin", key="login_pass")
    if st.button("Sign in", type="primary", use_container_width=True):
        if check_credentials(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = _clean_text(username)
            st.rerun()
        st.error("Invalid username or password.")
    st.caption("Default local demo account: admin / admin. Change it before deployment.")


def require_login() -> None:
    if not st.session_state.get("authenticated"):
        show_login_page()
        st.stop()
