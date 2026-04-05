import streamlit as st
import streamlit.components.v1 as _components
import os, json, time
from datetime import datetime
from dotenv import load_dotenv, set_key
import pandas as pd
from core.agents import BioPrecisionAgents
from auth import require_login

# ══ 页面配置（必须第一个 st 调用）══════════════════
st.set_page_config(page_title="Bio-Precision Agent v4", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if not os.path.exists(env_path):
    open(env_path, 'w').close()
load_dotenv(env_path)

require_login()

# ══ 悬浮侧边栏切换按钮（唯一真正能执行JS的方式）══
_components.html("""
<script>
(function(){
  // 操作父框架的 DOM（iframe -> 主页面）
  var doc = window.parent.document;

  function injectBtn(){
    if(doc.getElementById('bpa-tog')) return;
    var b = doc.createElement('button');
    b.id = 'bpa-tog';
    b.title = '展开 / 收起侧边栏';
    b.innerHTML = '<svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><rect y="1.5" width="15" height="1.5" rx="0.75" fill="#7b9ef8"/><rect y="6.75" width="15" height="1.5" rx="0.75" fill="#7b9ef8"/><rect y="12" width="15" height="1.5" rx="0.75" fill="#7b9ef8"/></svg>';
    b.style.cssText='position:fixed;top:11px;left:11px;z-index:2147483647;width:32px;height:32px;background:#1e2535;border:1px solid rgba(78,110,242,.4);border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,.5);transition:background .18s,border-color .18s;';
    b.onmouseenter=function(){this.style.background='#253047';this.style.borderColor='rgba(78,110,242,.7)';};
    b.onmouseleave=function(){this.style.background='#1e2535';this.style.borderColor='rgba(78,110,242,.4)';};
    b.onclick=function(){
      var sel=['[data-testid="collapsedControl"] button','[data-testid="stSidebarCollapseButton"] button','button[aria-label="Close sidebar"]','button[aria-label="Open sidebar"]'];
      for(var i=0;i<sel.length;i++){var el=doc.querySelector(sel[i]);if(el){el.click();return;}}
      // 备用：直接切换侧边栏 display
      var sb=doc.querySelector('section[data-testid="stSidebar"]');
      if(sb){sb.style.display=sb.style.display==='none'?'':'none';}
    };
    doc.body.appendChild(b);
  }

  injectBtn();
  // 监听 Streamlit 重渲染，防止按钮被清除
  new MutationObserver(injectBtn).observe(doc.body,{childList:true,subtree:false});
})();
</script>
""", height=0)

# ══ 全局 CSS（DeepSeek 风格）══════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ══════════════════════════════════════════════════
   基础 & 全局重置
══════════════════════════════════════════════════ */
html,body,.stApp{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif!important;
  background:#0e1117!important;
  color:#d4d8e1!important;
}
/* header 只做视觉透明，绝不改变 display/height/overflow
   因为 collapsedControl（侧边栏展开按钮）就渲染在 header 内部 */
header[data-testid="stHeader"]{
  background:transparent!important;
  box-shadow:none!important;
}
/* 只隐藏 header 内不需要的具体子元素 */
[data-testid="stToolbar"],[data-testid="stDecoration"],.stDeployButton,
#MainMenu,footer{
  display:none!important;
}

/* ══════════════════════════════════════════════════
   侧边栏主体
══════════════════════════════════════════════════ */
section[data-testid="stSidebar"]{
  background:#161b27!important;
  border-right:1px solid rgba(255,255,255,.06)!important;
}
section[data-testid="stSidebar"]>div:first-child{
  padding:10px 12px!important;
}
section[data-testid="stSidebar"] *{
  font-family:'Inter',sans-serif!important;
}

/* ── 侧边栏标题层级 ── */
section[data-testid="stSidebar"] h1{
  font-size:15px!important;font-weight:600!important;
  color:#e8eaf0!important;margin:0!important;padding:6px 4px!important;
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{
  font-size:11px!important;font-weight:600!important;
  color:#4a5568!important;text-transform:uppercase!important;
  letter-spacing:.9px!important;margin:0!important;padding:12px 4px 4px!important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stCaption p{
  font-size:12px!important;color:#4a5568!important;line-height:1.5!important;
}
section[data-testid="stSidebar"] label{
  color:#4a5568!important;font-size:11px!important;
  font-weight:600!important;text-transform:uppercase!important;letter-spacing:.5px!important;
}
section[data-testid="stSidebar"] hr{
  border-color:rgba(255,255,255,.06)!important;margin:10px 0!important;
}

/* ── 侧边栏普通按钮（历史记录列表等）── */
section[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;
  color:#8a95a8!important;
  border:1px solid transparent!important;
  text-align:left!important;
  padding:7px 10px!important;
  border-radius:8px!important;
  font-size:13px!important;
  transition:background .15s,color .15s!important;
  justify-content:flex-start!important;
  width:100%!important;
}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(78,110,242,.12)!important;
  color:#c5ccd9!important;
}
/* 主操作按钮（新查询）*/
section[data-testid="stSidebar"] .stButton>button[data-testid="baseButton-primary"]{
  background:linear-gradient(135deg,rgba(78,110,242,.18),rgba(123,108,246,.18))!important;
  color:#7b9ef8!important;
  border:1px solid rgba(78,110,242,.3)!important;
  font-weight:600!important;
}
section[data-testid="stSidebar"] .stButton>button[data-testid="baseButton-primary"]:hover{
  background:linear-gradient(135deg,rgba(78,110,242,.28),rgba(123,108,246,.28))!important;
  border-color:rgba(78,110,242,.5)!important;
}
/* 下载按钮 */
section[data-testid="stSidebar"] .stDownloadButton>button{
  background:rgba(255,255,255,.04)!important;
  color:#8a95a8!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:8px!important;
  font-size:13px!important;
  padding:7px 10px!important;
  transition:background .15s!important;
}
section[data-testid="stSidebar"] .stDownloadButton>button:hover{
  background:rgba(255,255,255,.08)!important;
  color:#c5ccd9!important;
}

/* ── 侧边栏输入框 ── */
section[data-testid="stSidebar"] .stTextInput>div>div>input{
  background:#1e2535!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:9px!important;
  color:#d4d8e1!important;
  font-size:13px!important;
  padding:8px 11px!important;
  transition:border-color .2s,box-shadow .2s!important;
}
section[data-testid="stSidebar"] .stTextInput>div>div>input:focus{
  border-color:rgba(78,110,242,.7)!important;
  box-shadow:0 0 0 3px rgba(78,110,242,.12)!important;
}
section[data-testid="stSidebar"] .stSelectbox>div>div{
  background:#1e2535!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:9px!important;
  color:#d4d8e1!important;
  font-size:13px!important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"]{
  border:1px dashed rgba(255,255,255,.1)!important;
  border-radius:10px!important;
  background:#1a2030!important;
}
section[data-testid="stSidebar"] .stAlert{
  background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.06)!important;
  border-radius:8px!important;font-size:12px!important;
}

/* ══════════════════════════════════════════════════
   侧边栏折叠/展开按钮 — 关键修复
   必须保证 z-index 足够高、pointer-events 开启
══════════════════════════════════════════════════ */
[data-testid="collapsedControl"]{
  background:#161b27!important;
  border-right:1px solid rgba(255,255,255,.06)!important;
  padding:14px 6px!important;
  z-index:99999!important;
  pointer-events:auto!important;
  position:relative!important;
}
[data-testid="collapsedControl"] button{
  background:#1e2535!important;
  border:1px solid rgba(78,110,242,.25)!important;
  border-radius:8px!important;
  color:#7b9ef8!important;
  width:30px!important;height:30px!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  transition:background .2s,border-color .2s!important;
  pointer-events:auto!important;
  cursor:pointer!important;
}
[data-testid="collapsedControl"] button:hover{
  background:#253047!important;
  border-color:rgba(78,110,242,.55)!important;
}
[data-testid="stSidebarCollapseButton"] button{
  background:#1e2535!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:8px!important;
  color:#8a95a8!important;
  width:30px!important;height:30px!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  transition:background .2s!important;
}
[data-testid="stSidebarCollapseButton"] button:hover{
  background:#253047!important;color:#d4d8e1!important;
}

/* ══════════════════════════════════════════════════
   主内容区
══════════════════════════════════════════════════ */
.main .block-container{
  max-width:860px!important;
  padding:40px 32px 100px!important;
  margin:0 auto!important;
}

/* ── 主区标题层级 ── */
.main h1{
  font-size:26px!important;font-weight:700!important;
  color:#e8eaf0!important;letter-spacing:-.5px!important;
  line-height:1.3!important;margin-bottom:6px!important;
}
.main h2{font-size:20px!important;font-weight:600!important;color:#e8eaf0!important;}
.main h3{font-size:15px!important;font-weight:600!important;color:#c5ccd9!important;}
.main h4{
  font-size:11px!important;font-weight:600!important;
  color:#4a5568!important;text-transform:uppercase!important;letter-spacing:.8px!important;
}
.main p,.main li,.stMarkdown p{
  color:#c5ccd9!important;font-size:15px!important;line-height:1.75!important;
}

/* ── 文本域 ── */
.stTextArea>div>div>textarea{
  background:#1a2030!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:14px!important;
  color:#d4d8e1!important;
  font-family:'Inter',sans-serif!important;
  font-size:15px!important;
  padding:14px 16px!important;
  line-height:1.65!important;
  transition:border-color .2s,box-shadow .2s!important;
  resize:vertical!important;
}
.stTextArea>div>div>textarea:focus{
  border-color:rgba(78,110,242,.7)!important;
  box-shadow:0 0 0 3px rgba(78,110,242,.12)!important;
}
.stTextArea>div>div>textarea::placeholder{color:#2d3a52!important;}
.stTextArea>label{color:#6b7688!important;font-size:13px!important;font-weight:500!important;}

/* ── 文本输入 ── */
.main .stTextInput>div>div>input{
  background:#1a2030!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:10px!important;
  color:#d4d8e1!important;font-size:14px!important;
  padding:10px 14px!important;
  transition:border-color .2s,box-shadow .2s!important;
}
.main .stTextInput>div>div>input:focus{
  border-color:rgba(78,110,242,.7)!important;
  box-shadow:0 0 0 3px rgba(78,110,242,.12)!important;
}
.main .stTextInput>label{color:#6b7688!important;font-size:12px!important;font-weight:500!important;}

/* ── 下拉选择 ── */
.main .stSelectbox>div>div{
  background:#1a2030!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:10px!important;color:#d4d8e1!important;font-size:14px!important;
}
.main .stSelectbox>label{color:#6b7688!important;font-size:12px!important;font-weight:500!important;}

/* ── 主按钮 ── */
.main .stButton>button{
  font-family:'Inter',sans-serif!important;
  border-radius:10px!important;font-size:14px!important;
  font-weight:500!important;transition:all .2s!important;
}
.main .stButton>button[data-testid="baseButton-primary"]{
  background:linear-gradient(135deg,#4e6ef2,#7b6cf6)!important;
  color:#fff!important;border:none!important;
  padding:11px 22px!important;
  box-shadow:0 2px 16px rgba(78,110,242,.35)!important;
}
.main .stButton>button[data-testid="baseButton-primary"]:hover{
  background:linear-gradient(135deg,#3d5ce0,#6a5be4)!important;
  box-shadow:0 4px 20px rgba(78,110,242,.5)!important;
  transform:translateY(-1px)!important;
}
.main .stButton>button[data-testid="baseButton-secondary"]{
  background:rgba(255,255,255,.04)!important;
  color:#c5ccd9!important;
  border:1px solid rgba(255,255,255,.08)!important;
  padding:10px 20px!important;
}
.main .stButton>button[data-testid="baseButton-secondary"]:hover{
  background:rgba(255,255,255,.08)!important;color:#e8eaf0!important;
}

/* ── 下载按钮 ── */
.stDownloadButton>button{
  background:rgba(255,255,255,.04)!important;
  color:#c5ccd9!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:10px!important;
  font-family:'Inter',sans-serif!important;font-size:13px!important;
  font-weight:500!important;transition:all .2s!important;
}
.stDownloadButton>button:hover{
  background:rgba(78,110,242,.12)!important;color:#e8eaf0!important;
  border-color:rgba(78,110,242,.3)!important;transform:translateY(-1px)!important;
}

/* ── 提示框 ── */
.stAlert{border-radius:12px!important;font-family:'Inter',sans-serif!important;font-size:14px!important;}
[data-testid="stNotificationContentInfo"]{background:rgba(78,110,242,.08)!important;border-color:rgba(78,110,242,.2)!important;}
[data-testid="stNotificationContentWarning"]{background:rgba(245,158,11,.07)!important;}
[data-testid="stNotificationContentError"]{background:rgba(239,68,68,.07)!important;}
[data-testid="stNotificationContentSuccess"]{background:rgba(34,197,94,.07)!important;}

/* ── 带边框容器 ── */
[data-testid="stVerticalBlockBorderWrapper"]>div{
  background:#141922!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:16px!important;padding:20px!important;
}

/* ── 折叠面板 ── */
[data-testid="stExpander"]{
  background:#141922!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:12px!important;overflow:hidden!important;
}
[data-testid="stExpander"] summary{
  color:#c5ccd9!important;font-family:'Inter',sans-serif!important;
  font-size:14px!important;padding:12px 16px!important;
}
[data-testid="stExpander"] summary:hover{background:rgba(78,110,242,.06)!important;}

/* ── 状态组件 ── */
[data-testid="stStatusWidget"]{
  background:#141922!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:12px!important;
}
[data-testid="stStatusWidget"] p{font-size:13px!important;}

/* ── 数据编辑器 ── */
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{
  background:#141922!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:12px!important;overflow:hidden!important;
}

/* ── 分隔线 ── */
hr{border-color:rgba(255,255,255,.06)!important;margin:24px 0!important;}

/* ── 文件上传 ── */
[data-testid="stFileUploader"]{
  background:#141922!important;
  border:1px dashed rgba(255,255,255,.1)!important;
  border-radius:12px!important;
}

/* ── 代码块 ── */
.stMarkdown code{
  background:#111827!important;color:#a5b4fc!important;
  border-radius:5px!important;padding:1px 6px!important;font-size:13px!important;
}
.stMarkdown pre{
  background:#111827!important;border-radius:12px!important;
  border:1px solid rgba(255,255,255,.07)!important;padding:16px!important;
}
.stMarkdown pre code{background:transparent!important;padding:0!important;}
.stMarkdown table{border-collapse:collapse!important;width:100%!important;}
.stMarkdown th{
  background:#1a2030!important;color:#6b7688!important;
  font-size:12px!important;font-weight:600!important;text-transform:uppercase!important;
  letter-spacing:.5px!important;padding:10px 14px!important;
  border-bottom:1px solid rgba(255,255,255,.08)!important;
}
.stMarkdown td{
  padding:10px 14px!important;
  border-bottom:1px solid rgba(255,255,255,.05)!important;
  color:#c5ccd9!important;font-size:14px!important;
}
.stMarkdown tr:hover td{background:rgba(78,110,242,.05)!important;}
.stMarkdown h1,.stMarkdown h2{border-bottom:1px solid rgba(255,255,255,.06)!important;padding-bottom:8px!important;}

/* ── 滚动条 ── */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:rgba(78,110,242,.3);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:rgba(78,110,242,.5);}

/* ── 文件上传器文字 ── */
[data-testid="stFileUploader"] *{color:#4a5568!important;}
[data-testid="stFileUploaderDropzoneInstructions"] *{font-size:13px!important;}

/* ── 隐藏侧边栏关闭按钮的文字标签（避免显示 Keyboard_double 等内置标签）── */
[data-testid="stSidebarCollapseButton"] button span,
[data-testid="stSidebarCollapseButton"] button svg + span,
[data-testid="stSidebarCollapseButton"] .st-emotion-cache-dvn5ps,
button[aria-label="Close sidebar"] span:not(:has(svg)),
button[aria-label="Open sidebar"] span:not(:has(svg)){
  display:none!important;
  width:0!important;height:0!important;overflow:hidden!important;
}
</style>
""", unsafe_allow_html=True)

# ══ 历史记录（服务端存储）══════════════════════════
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

def _history_file() -> str:
    return os.path.join(HISTORY_DIR, f"{st.session_state.get('username','default')}.json")

def save_to_history(prompt, report, evidence=""):
    history = load_history()
    history.insert(0, {
        "id": int(time.time()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": prompt[:30] + ("..." if len(prompt) > 30 else ""),
        "prompt": prompt, "report": report, "evidence": evidence,
    })
    with open(_history_file(), 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_history() -> list:
    p = _history_file()
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def delete_all_history():
    p = _history_file()
    if os.path.exists(p): os.remove(p)

# ══ 导出工具 ══════════════════════════════════════
def extract_bom_csv(md: str):
    import csv, io
    lines = [l.strip() for l in md.split('\n') if l.strip().startswith('|') and len(l.split('|')) > 2]
    if len(lines) < 2: return None
    if '---' in lines[1]: lines.pop(1)
    out = io.StringIO()
    w = csv.writer(out)
    for line in lines:
        w.writerow([c.strip() for c in line.split('|')[1:-1]])
    return out.getvalue().encode('utf-8-sig')

def create_notebook(md: str) -> str:
    import nbformat as nbf, re
    nb = nbf.v4.new_notebook(); cells = []
    parts = re.split(r'```(python|bash|r)\n([\s\S]*?)```', md, flags=re.IGNORECASE)
    if parts[0].strip(): cells.append(nbf.v4.new_markdown_cell(parts[0]))
    for i in range(1, len(parts), 3):
        cells.append(nbf.v4.new_code_cell(parts[i+1].strip()))
        if parts[i+2].strip(): cells.append(nbf.v4.new_markdown_cell(parts[i+2].strip()))
    nb.cells = cells
    return nbf.writes(nb)

def history_to_json() -> bytes:
    return json.dumps(load_history(), ensure_ascii=False, indent=2).encode('utf-8')

# ══ 侧边栏 ════════════════════════════════════════
with st.sidebar:
    username = st.session_state.get("username", "user")
    
    # 品牌 Logo
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:8px 4px 16px;">
      <div style="width:32px;height:32px;background:linear-gradient(145deg,#4e6ef2,#7b6cf6);
        border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;
        box-shadow:0 4px 12px rgba(78,110,242,.35);flex-shrink:0;">🧬</div>
      <div>
        <div style="font-size:14px;font-weight:600;color:#ececec;font-family:'Inter',sans-serif;">BPA v4</div>
        <div style="font-size:11px;color:#555;font-family:'Inter',sans-serif;">@{username}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 本地/远程检测
    _host = st.context.headers.get("host", "")
    _is_local = _host.startswith("localhost") or _host.startswith("127.0.0.1")

    saved_api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if _is_local:
        st.markdown("---")
        api_key = st.text_input("DeepSeek API Key", value=saved_api_key, type="password")
        if st.button("💾 保存 API Key"):
            if api_key:
                set_key(env_path, "DEEPSEEK_API_KEY", api_key)
                st.success("✅ 保存成功")
            else:
                st.error("请输入 API Key")
    else:
        api_key = saved_api_key
        if not api_key:
            st.warning("⚠️ 未配置 API Key，请联系管理员")

    st.markdown("---")
    model_choice = st.selectbox("AI 模型", ["deepseek-chat", "deepseek-reasoner"],
        help="chat 速度快；reasoner 推理更深入但略慢")

    st.markdown("---")
    st.subheader("📎 参考文献")
    st.caption("上传 PDF 论文，AI 将优先参考其中的方法和参数")
    uploaded_file = st.file_uploader("选择 PDF 文件", type="pdf", label_visibility="collapsed")
    pdf_text = ""
    if uploaded_file:
        try:
            import PyPDF2
            r = PyPDF2.PdfReader(uploaded_file)
            for page in r.pages:
                t = page.extract_text()
                if t: pdf_text += t + "\n"
            st.success("✅ PDF 已加载")
        except Exception as e:
            st.error(f"读取失败: {e}")

    st.markdown("---")
    st.subheader("📜 历史记录")
    st.caption("所有记录保存于服务器，可随时查看或导出")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🆕 新查询", width='stretch', type="primary"):
            for k in ['phase','last_report','last_evidence']:
                st.session_state[k] = 0 if k == 'phase' else ""
            st.rerun()
    with c2:
        st.download_button("📤 导出", data=history_to_json(),
            file_name=f"bpa_{username}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json", width='stretch')

    history_data = load_history()
    if history_data:
        for item in history_data:
            label = f"🕐 {item['timestamp'][:10]}  {item['title']}"
            if st.button(label, key=f"h_{item['id']}", width='stretch'):
                st.session_state.update({
                    'prompt': item['prompt'], 'last_report': item['report'],
                    'last_evidence': item.get('evidence',''), 'phase': 0
                })
                st.rerun()

        st.markdown("---")
        if _is_local:
            if st.button("🗑️ 删除全部历史", width='stretch'):
                delete_all_history()
                st.success("已清空")
                st.rerun()
    else:
        st.caption("暂无历史记录")

    st.markdown("---")
    if st.button("退出登录", width='stretch'):
        st.session_state.clear()
        st.rerun()

# ══ 主界面 ════════════════════════════════════════

# 初始化状态
for k, v in [('prompt',''),('last_report',''),('last_evidence',''),('raw_chunks',[]),('phase',0),('architect_data',{})]:
    if k not in st.session_state: st.session_state[k] = v

# 顶部标题
st.markdown("""
<div style="margin-bottom:8px;">
  <h1 style="margin:0;">🔬 Bio-Precision Agent</h1>
  <p style="margin:6px 0 0;font-size:15px;color:#6b6b6b;">
    描述实验想法 → 自动查阅 PubMed 文献 → 生成完整实验方案
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# 示例按钮
if st.button("💡 填入示例：拟南芥光响应途径基因查询"):
    st.session_state.prompt = "拟南芥光响应途径都有哪些基因？请列出主要成员并说明其功能与调控关系"

prompt = st.text_area(
    "✍️ 请描述您的实验目的：",
    value=st.session_state.prompt, height=130,
    placeholder="例如：拟南芥光响应途径都有哪些基因？请列出主要成员并说明其功能与调控关系"
)

# ── 第一步 ────────────────────────────────────────
if st.session_state.phase == 0:
    if st.button("🚀 开始分析我的实验需求", type="primary"):
        if not api_key:
            st.error("⚠️ 未找到 API Key，请联系管理员配置。")
            st.stop()
        if not prompt.strip():
            st.warning("⚠️ 请先填写实验需求描述。")
            st.stop()
        system = BioPrecisionAgents(api_key=api_key, model_name=model_choice)
        st.session_state.system = system
        with st.status("🤖 正在解析您的实验需求...", expanded=True) as s:
            st.write("正在读取并理解您的实验描述...")
            st.write("提取需要查阅文献的关键问题...")
            try:
                data = system.run_architect(prompt, pdf_text)
                st.write("✓ 解析完成，请在下方核对信息")
                s.update(label="✅ 需求解析完成，请确认下方信息后继续", state="complete", expanded=False)
                st.session_state.architect_data = data
                st.session_state.phase = 1
                st.rerun()
            except Exception as e:
                s.update(label=f"❌ 解析失败：{e}", state="error")
                st.stop()

# ── 第二步：确认信息 ───────────────────────────────
if st.session_state.phase >= 1:
    st.markdown("### ✅ 请确认 AI 解析的信息是否准确")
    st.info("请检查以下信息是否正确，可直接修改，确认后点击按钮开始查阅文献。")

    arch = st.session_state.architect_data

    with st.container(border=True):
        st.markdown("#### 基本实验信息")
        c1, c2 = st.columns(2)
        with c1:
            species = st.text_input(
                "目标物种（尽量填拉丁学名，如 Dendrocalamus latiflorus）",
                value=arch.get('Species','未知'))
        with c2:
            opt = arch.get('Experiment_Type','wet')
            if opt not in ['wet','dry','mixed']: opt = 'wet'
            exp_type = st.selectbox(
                '实验类型（选"生信代码"或"混合"可额外下载 Python 代码）',
                ['wet (湿实验)','dry (生信代码)','mixed (混合实验)'],
                index=['wet','dry','mixed'].index(opt))
        goal = st.text_input("🎯 实验目标（一句话描述科学问题）", value=arch.get('Key_Goal','未知'))

    with st.container(border=True):
        st.markdown("#### 🔍 需重点查阅文献的关键参数")
        st.caption("系统认为需要文献支撑才能确认的问题，可直接修改或添加。")
        params_list = arch.get('Params',[]) or [""]
        df = pd.DataFrame({"关键参数（如：诱导激素浓度、差异表达分析方法等）": params_list})
        edited_df = st.data_editor(df, num_rows="dynamic", width='stretch')

    if st.session_state.phase == 1:
        if st.button("🔍 确认无误，开始查阅文献并生成方案 →", type="primary", width='stretch'):
            st.session_state.architect_data.update({
                'Species': species,
                'Experiment_Type': exp_type.split(" ")[0],
                'Key_Goal': goal,
                'Params': edited_df.iloc[:,0].dropna().tolist()
            })
            st.session_state.phase = 2
            st.rerun()

# ── 第三步：查文献 + 生成方案 ─────────────────────
if st.session_state.phase == 2:
    st.markdown("---")
    system = st.session_state.system
    c_res, c_val = st.columns(2)

    with c_res:
        with st.status("📚 正在查阅 PubMed 文献...", expanded=True) as s_res:
            st.write("连接 PubMed 数据库，检索相关论文...")
            st.write("搜索网络上的公开实验方案...")
            st.write("整理文献内容，准备交给 AI 分析...")
            try:
                researcher_result = system.run_researcher(prompt, st.session_state.architect_data, pdf_text)
                st.session_state.last_evidence = researcher_result["synthesis"]
                st.session_state.raw_chunks = researcher_result["chunks"]
                s_res.update(label="✅ 文献查阅完成", state="complete", expanded=False)
            except Exception as e:
                s_res.update(label=f"❌ 文献查阅失败：{e}", state="error"); st.stop()

    with c_val:
        with st.status("📝 正在生成实验方案...", expanded=True) as s_val:
            st.write("核对文献数据，确保参数准确可信...")
            st.write("整理实验步骤和操作流程...")
            st.write("生成试剂清单，准备代码文件...")
            try:
                report = system.run_validator(
                    prompt,
                    st.session_state.architect_data,
                    {
                        "synthesis": st.session_state.last_evidence,
                        "chunks": st.session_state.raw_chunks,
                    }
                )
                s_val.update(label="✅ 实验方案生成完毕！", state="complete", expanded=False)
                st.session_state.last_report = report
                save_to_history(prompt, report, st.session_state.last_evidence)
                st.session_state.phase = 0
            except Exception as e:
                s_val.update(label=f"❌ 方案生成失败：{e}", state="error"); st.stop()
        st.rerun()

# ══ 报告区域 ══════════════════════════════════════
if st.session_state.last_report:
    st.markdown("---")

    rep_col, ev_col = st.columns([7, 3])

    with rep_col:
        st.markdown("## 📄 实验方案报告")
        st.markdown(st.session_state.last_report, unsafe_allow_html=True)

    with ev_col:
        st.markdown("### 🔎 文献参考来源")
        st.info("左侧为最终方案，右侧为系统检索到的原始文献内容及 AI 综合分析。")
        if st.session_state.last_evidence:
            with st.expander("展开查看 AI 证据综合分析"):
                st.text(st.session_state.last_evidence)
        else:
            st.caption("暂无综合分析记录")
        if st.session_state.raw_chunks:
            with st.expander("展开查看原始文献片段"):
                for i, chunk in enumerate(st.session_state.raw_chunks):
                    st.markdown(f"**{i+1}. {chunk.source_type.upper()}** `{chunk.source_id}`")
                    st.caption(f"检索词: {chunk.query}")
                    st.text(chunk.content[:800] + ("..." if len(chunk.content) > 800 else ""))
                    st.markdown("---")
        else:
            st.caption("暂无原始文献片段")

    st.markdown("---")
    st.markdown("### 📥 下载报告与相关文件")

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.download_button("📝 Markdown 文档", data=st.session_state.last_report,
            file_name="protocol.md", mime="text/markdown", width='stretch')
    with d2:
        try:
            from markdown_pdf import MarkdownPdf, Section
            import tempfile, re
            def _fix_code(m):
                lang=m.group(1).strip(); code=m.group(2).strip()
                blk=f"\n<br/>**[{lang} 代码]**\n"
                for ln in code.split('\n'): blk+=f"> ``` {ln} ```\n"
                return blk+"\n<br/>\n"
            rpt = re.sub(r'```([a-zA-Z]*)\n([\s\S]*?)```', _fix_code, st.session_state.last_report)
            pdf = MarkdownPdf(toc_level=2); pdf.add_section(Section(rpt))
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp: tp=tmp.name
            pdf.save(tp)
            with open(tp,"rb") as f: pb=f.read()
            st.download_button("🖨️ PDF 文档", data=pb, file_name="protocol.pdf",
                mime="application/pdf", width='stretch')
            if os.path.exists(tp): os.remove(tp)
        except Exception:
            st.button("🖨️ PDF 生成失败", disabled=True, width='stretch')
    with d3:
        bom = extract_bom_csv(st.session_state.last_report)
        if bom:
            st.download_button("📦 试剂清单 CSV", data=bom,
                file_name="reagents.csv", mime="text/csv", width='stretch')
        else:
            st.button("📦 未检测到试剂清单", disabled=True, width='stretch')
    with d4:
        etype = st.session_state.architect_data.get('Experiment_Type','')
        if etype in ['dry','mixed']:
            try:
                nb = create_notebook(st.session_state.last_report)
                st.download_button("💻 分析代码 .ipynb", data=nb,
                    file_name="analysis.ipynb", mime="application/x-ipynb+json", width='stretch')
            except Exception:
                st.button("💻 代码生成失败", disabled=True, width='stretch')
        else:
            st.button("💻 无代码（纯湿实验）", disabled=True, width='stretch')
