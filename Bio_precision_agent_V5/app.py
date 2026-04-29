from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv, set_key

from auth import require_login
from core.agents import BioPrecisionAgents
from core.config import DEEPSEEK_DEFAULT_MODEL, ENV_PATH, HISTORY_DIR, ensure_runtime_dirs


st.set_page_config(
    page_title="Bio-Precision Agent V5",
    page_icon="BP",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_runtime_dirs()
load_dotenv(ENV_PATH)
require_login()


APP_CSS = """
<style>
html, body, .stApp {
  background: #0f131b !important;
  color: #d9deea !important;
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif !important;
}
header[data-testid="stHeader"], #MainMenu, footer,
[data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton {
  display: none !important;
}
.main .block-container {
  max-width: 1120px !important;
  padding: 34px 34px 90px !important;
}
section[data-testid="stSidebar"] {
  background: #151b27 !important;
  border-right: 1px solid rgba(255,255,255,.07) !important;
}
.stButton button, .stDownloadButton button {
  border-radius: 8px !important;
}
.stTextArea textarea, .stTextInput input {
  background: #171f2d !important;
  color: #e8ecf4 !important;
  border: 1px solid rgba(255,255,255,.10) !important;
  border-radius: 8px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
  background: #131925 !important;
  border: 1px solid rgba(255,255,255,.08) !important;
  border-radius: 8px !important;
}
.stMarkdown code {
  background: #111827 !important;
  color: #a5b4fc !important;
  border-radius: 5px !important;
  padding: 1px 5px !important;
}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)


def history_file() -> str:
    username = st.session_state.get("username", "default")
    return str(HISTORY_DIR / f"{username}.json")


def load_history() -> list:
    path = history_file()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []


def save_to_history(prompt: str, report: str, evidence: str) -> None:
    history = load_history()
    history.insert(
        0,
        {
            "id": int(time.time()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": prompt[:54] + ("..." if len(prompt) > 54 else ""),
            "prompt": prompt,
            "report": report,
            "evidence": evidence,
        },
    )
    with open(history_file(), "w", encoding="utf-8") as handle:
        json.dump(history[:60], handle, ensure_ascii=False, indent=2)


def delete_history() -> None:
    path = history_file()
    if os.path.exists(path):
        os.remove(path)


def history_json() -> bytes:
    return json.dumps(load_history(), ensure_ascii=False, indent=2).encode("utf-8")


def extract_bom_csv(markdown: str):
    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return None
    output = io.StringIO()
    writer = csv.writer(output)
    for line in lines:
        if re.fullmatch(r"\|[\s:\-]+\|", line):
            continue
        writer.writerow([cell.strip() for cell in line.split("|")[1:-1]])
    return output.getvalue().encode("utf-8-sig")


def create_notebook(markdown: str) -> str:
    import nbformat as nbf

    notebook = nbf.v4.new_notebook()
    cells = []
    parts = re.split(r"```(python|bash|r)\n([\s\S]*?)```", markdown, flags=re.IGNORECASE)
    if parts[0].strip():
        cells.append(nbf.v4.new_markdown_cell(parts[0].strip()))
    for index in range(1, len(parts), 3):
        cells.append(nbf.v4.new_code_cell(parts[index + 1].strip()))
        if parts[index + 2].strip():
            cells.append(nbf.v4.new_markdown_cell(parts[index + 2].strip()))
    notebook.cells = cells
    return nbf.writes(notebook)


def read_pdf(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except Exception as exc:
        st.error(f"PDF extraction failed: {exc}")
        return ""


for key, value in {
    "prompt": "",
    "phase": 0,
    "architect_data": {},
    "last_report": "",
    "last_evidence": "",
    "raw_chunks": [],
}.items():
    st.session_state.setdefault(key, value)


with st.sidebar:
    username = st.session_state.get("username", "user")
    st.title("BPA V5")
    st.caption(f"Signed in as {username}")

    host = st.context.headers.get("host", "")
    is_local = host.startswith("localhost") or host.startswith("127.0.0.1") or host == ""
    saved_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    api_key = saved_api_key

    st.divider()
    st.subheader("DeepSeek")
    if is_local:
        api_key = st.text_input("API key", value=saved_api_key, type="password")
        if st.button("Save API key", use_container_width=True):
            if api_key:
                set_key(str(ENV_PATH), "DEEPSEEK_API_KEY", api_key)
                st.success("API key saved.")
            else:
                st.error("Enter an API key first.")
    elif not api_key:
        st.warning("No API key is configured on this server.")

    model_choice = st.selectbox("Model", [DEEPSEEK_DEFAULT_MODEL])
    thinking_enabled = st.toggle(
        "Deep thinking",
        value=False,
        help="Keep this off for faster V4 Flash runs. Enable it for complex review tasks.",
    )

    st.divider()
    st.subheader("Reference PDF")
    uploaded_file = st.file_uploader("Upload a text-based PDF", type="pdf", label_visibility="collapsed")
    pdf_text = read_pdf(uploaded_file)
    if pdf_text:
        st.success("PDF text loaded.")

    st.divider()
    st.subheader("History")
    if st.button("New analysis", type="primary", use_container_width=True):
        for key in ("prompt", "last_report", "last_evidence", "raw_chunks", "architect_data"):
            st.session_state[key] = [] if key == "raw_chunks" else ""
        st.session_state.phase = 0
        st.rerun()

    st.download_button(
        "Export history",
        data=history_json(),
        file_name=f"bpa_v5_{username}_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        use_container_width=True,
    )

    for item in load_history():
        if st.button(item["title"], key=f"history_{item['id']}", use_container_width=True):
            st.session_state.prompt = item["prompt"]
            st.session_state.last_report = item["report"]
            st.session_state.last_evidence = item.get("evidence", "")
            st.session_state.phase = 0
            st.rerun()

    if is_local and st.button("Delete local history", use_container_width=True):
        delete_history()
        st.success("History deleted.")
        st.rerun()

    st.divider()
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()


st.title("Bio-Precision Agent V5")
st.caption("Evidence-grounded biomedical protocol generation with PubMed, web retrieval, uploaded PDFs, and citation auditing.")

example = (
    "Design a differential expression workflow for the DREB gene family in bamboo. "
    "Identify key evidence-backed analysis steps, recommended packages, and validation checkpoints."
)
if st.button("Load example"):
    st.session_state.prompt = example

prompt = st.text_area(
    "Research goal",
    value=st.session_state.prompt,
    height=140,
    placeholder="Describe the wet-lab, dry-lab, or mixed biomedical workflow you want to design.",
)


if st.session_state.phase == 0:
    if st.button("Analyze requirements", type="primary"):
        if not api_key:
            st.error("Configure a DeepSeek API key first.")
            st.stop()
        if not prompt.strip():
            st.warning("Describe a research goal first.")
            st.stop()
        thinking_mode = "enabled" if thinking_enabled else "disabled"
        system = BioPrecisionAgents(api_key=api_key, model_name=model_choice, thinking_mode=thinking_mode)
        st.session_state.system = system
        with st.status("Parsing research requirements...", expanded=True) as status:
            try:
                data = system.run_architect(prompt, pdf_text)
                st.session_state.architect_data = data
                st.session_state.phase = 1
                status.update(label="Requirement parsing complete.", state="complete", expanded=False)
                st.rerun()
            except Exception as exc:
                status.update(label=f"Requirement parsing failed: {exc}", state="error")
                st.stop()


if st.session_state.phase >= 1:
    st.divider()
    st.subheader("Confirm structured requirements")
    architecture = st.session_state.architect_data
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            species = st.text_input("Target species", value=architecture.get("Species", "Unknown"))
        with right:
            current_type = architecture.get("Experiment_Type", "mixed")
            if current_type not in ("wet", "dry", "mixed"):
                current_type = "mixed"
            experiment_type = st.selectbox(
                "Experiment type",
                ["wet", "dry", "mixed"],
                index=["wet", "dry", "mixed"].index(current_type),
            )
        key_goal = st.text_input("Core objective", value=architecture.get("Key_Goal", ""))

    params = architecture.get("Params") or [""]
    edited = st.data_editor(
        pd.DataFrame({"Evidence question": params}),
        num_rows="dynamic",
        use_container_width=True,
    )

    if st.session_state.phase == 1 and st.button("Retrieve evidence and generate protocol", type="primary"):
        st.session_state.architect_data = {
            "Species": species,
            "Experiment_Type": experiment_type,
            "Key_Goal": key_goal,
            "Params": edited.iloc[:, 0].dropna().astype(str).str.strip().replace("", pd.NA).dropna().tolist(),
        }
        st.session_state.phase = 2
        st.rerun()


if st.session_state.phase == 2:
    st.divider()
    system = st.session_state.get("system")
    if system is None:
        thinking_mode = "enabled" if thinking_enabled else "disabled"
        system = BioPrecisionAgents(api_key=api_key, model_name=model_choice, thinking_mode=thinking_mode)

    left, right = st.columns(2)
    with left:
        with st.status("Retrieving and synthesizing evidence...", expanded=True) as status:
            try:
                research = system.run_researcher(prompt, st.session_state.architect_data, pdf_text)
                st.session_state.last_evidence = research["synthesis"]
                st.session_state.raw_chunks = research["chunks"]
                st.session_state.research_result = research
                status.update(label="Evidence synthesis complete.", state="complete", expanded=False)
            except Exception as exc:
                status.update(label=f"Evidence retrieval failed: {exc}", state="error")
                st.stop()

    with right:
        with st.status("Validating claims and writing protocol...", expanded=True) as status:
            try:
                report = system.run_validator(prompt, st.session_state.architect_data, st.session_state.research_result)
                st.session_state.last_report = report
                save_to_history(prompt, report, st.session_state.last_evidence)
                st.session_state.phase = 0
                status.update(label="Protocol generated.", state="complete", expanded=False)
            except Exception as exc:
                status.update(label=f"Protocol generation failed: {exc}", state="error")
                st.stop()
    st.rerun()


if st.session_state.last_report:
    st.divider()
    report_col, evidence_col = st.columns([7, 3])
    with report_col:
        st.subheader("Protocol report")
        st.markdown(st.session_state.last_report)

    with evidence_col:
        st.subheader("Evidence panel")
        if st.session_state.last_evidence:
            with st.expander("Researcher synthesis", expanded=False):
                st.text(st.session_state.last_evidence)
        if st.session_state.raw_chunks:
            with st.expander("Raw evidence chunks", expanded=False):
                for index, chunk in enumerate(st.session_state.raw_chunks, start=1):
                    st.markdown(f"**{index}. {chunk.source_type.upper()}** `{chunk.source_id or chunk.url}`")
                    st.caption(f"Query: {chunk.query} | Trust score: {chunk.trust_score}")
                    st.text(chunk.content[:900] + ("..." if len(chunk.content) > 900 else ""))
                    st.divider()

    st.subheader("Downloads")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.download_button("Markdown", st.session_state.last_report, "protocol_v5.md", "text/markdown", use_container_width=True)
    with d2:
        bom = extract_bom_csv(st.session_state.last_report)
        if bom:
            st.download_button("BOM CSV", bom, "bom_v5.csv", "text/csv", use_container_width=True)
        else:
            st.button("No BOM detected", disabled=True, use_container_width=True)
    with d3:
        if st.session_state.architect_data.get("Experiment_Type") in {"dry", "mixed"}:
            st.download_button(
                "Notebook",
                create_notebook(st.session_state.last_report),
                "analysis_v5.ipynb",
                "application/x-ipynb+json",
                use_container_width=True,
            )
        else:
            st.button("No notebook needed", disabled=True, use_container_width=True)
    with d4:
        st.download_button(
            "Evidence JSON",
            json.dumps([chunk.__dict__ for chunk in st.session_state.raw_chunks], ensure_ascii=False, indent=2),
            "evidence_v5.json",
            "application/json",
            use_container_width=True,
        )
