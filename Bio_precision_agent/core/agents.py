import os
import json
import re
from typing import List, Dict, Any
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from .prompts import ARCHITECT_PROMPT, RESEARCHER_PROMPT, VALIDATOR_PROMPT
from .researcher import orchestrate_research, EvidenceChunk


class ArchitectOutput(BaseModel):
    Experiment_Type: str = Field(description="'wet', 'dry', or 'mixed'")
    Species: str = Field(description="Target organism species")
    Key_Goal: str = Field(description="The core objective of the experiment")
    Params: List[str] = Field(description="List of highly specific parameters that must be determined")

    @classmethod
    def validate_and_clean(cls, raw_data: dict) -> dict:
        """增强清洗：处理常见 LLM 输出偏差。"""
        data = dict(raw_data)
        # 标准化 Experiment_Type
        et = str(data.get("Experiment_Type", "mixed")).lower().strip()
        if et not in ("wet", "dry", "mixed"):
            et = "mixed"
        data["Experiment_Type"] = et

        # 确保 Params 是字符串列表
        params = data.get("Params", [])
        if isinstance(params, str):
            params = [params]
        elif not isinstance(params, list):
            params = []
        cleaned_params = []
        for p in params:
            s = str(p).strip()
            if s and s.lower() not in ("none", "null", "nan"):
                cleaned_params.append(s)
        data["Params"] = cleaned_params

        # 确保字符串字段
        for key in ("Species", "Key_Goal"):
            val = data.get(key, "")
            if val is None:
                val = ""
            data[key] = str(val).strip()
        return data


class BioPrecisionAgents:
    def __init__(self, api_key: str, model_name: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model_name = model_name

    def run_architect(self, user_input: str, pdf_text: str = "") -> dict:
        """
        Phase 1: Semantic Parsing with strict Pydantic validation.
        """
        extra_ctx = (
            f"\n\n--- UPLOADED PDF CONTEXT ---\n{pdf_text[:8000]}"
            if pdf_text else ""
        )
        prompt = (
            f"User Intent: {user_input}{extra_ctx}\n\n"
            "Please output ONLY valid JSON matching this schema: "
            "{ 'Experiment_Type': str, 'Species': str, 'Key_Goal': str, 'Params': [str, str, ...] }"
        )

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": ARCHITECT_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        try:
            text = response.choices[0].message.content.strip()
            data = json.loads(text)
            cleaned = ArchitectOutput.validate_and_clean(data)
            # Pydantic 最终校验
            validated = ArchitectOutput.model_validate(cleaned)
            return validated.model_dump()
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(
                f"Architect parsing failed: {e}\nResponse was: {response.choices[0].message.content}"
            )

    def run_researcher(self, user_input: str, architect_data: dict, pdf_text: str = "") -> dict:
        """
        Phase 2: Evidence Synthesis with optional self-correction loop.
        返回字典，包含 synthesis（字符串）和 chunks（原始证据列表）。
        """
        species = architect_data.get("Species", "")
        key_goal = architect_data.get("Key_Goal", "")
        params = architect_data.get("Params", [])

        # 初始检索
        research_result = orchestrate_research(params, species, key_goal, pdf_text)
        raw_chunks: List[EvidenceChunk] = research_result["chunks"]
        summary_text = research_result["summary_text"]

        # 第一轮合成
        synthesis = self._call_researcher_synthesizer(user_input, params, summary_text)

        # 检查是否需要补充检索
        follow_up = self._extract_follow_up_queries(synthesis)
        if follow_up:
            # 执行补充检索
            supplemental_chunks: List[EvidenceChunk] = []
            for q in follow_up:
                from .researcher import fetch_pubmed_abstracts, get_duckduckgo_search_results
                pub_chunks, _ = fetch_pubmed_abstracts(q, max_results=2)
                supplemental_chunks.extend(pub_chunks)
                web_chunks = get_duckduckgo_search_results(q, max_results=2)
                supplemental_chunks.extend(web_chunks)
            # 去重并截断
            from .researcher import _deduplicate_chunks, _truncate_chunks
            raw_chunks.extend(supplemental_chunks)
            raw_chunks = _deduplicate_chunks(raw_chunks)
            raw_chunks = _truncate_chunks(raw_chunks, max_total_chars=22000)
            # 重新生成 summary_text
            summary_lines = [c.to_text() for c in raw_chunks]
            summary_text = "\n".join(summary_lines)
            # 第二轮合成
            synthesis = self._call_researcher_synthesizer(user_input, params, summary_text)

        return {
            "synthesis": synthesis,
            "chunks": raw_chunks,
        }

    def _call_researcher_synthesizer(self, user_input: str, params: List[str], evidence_text: str) -> str:
        prompt = (
            f"User Intent: {user_input}\n"
            f"Params to Find: {params}\n\n"
            f"Evidence Corpus:\n{evidence_text}\n\n"
            "Please synthesize the evidence according to your instructions. "
            "If you believe additional targeted searches are needed for specific parameters, "
            "list them under a section exactly titled 'FOLLOW_UP_QUERIES:' with one query per line."
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": RESEARCHER_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

    @staticmethod
    def _extract_follow_up_queries(text: str) -> List[str]:
        """提取 Researcher 要求的补充检索查询。"""
        pattern = re.search(r"FOLLOW_UP_QUERIES:(.*?)(?:\n# |\n---|\Z)", text, re.DOTALL | re.IGNORECASE)
        if not pattern:
            return []
        block = pattern.group(1)
        queries = []
        for line in block.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # 去掉常见的列表符号
            line = re.sub(r"^[\-\*\d]+[\.\)]\s*", "", line)
            if line and len(line) > 5:
                queries.append(line)
        return queries[:3]  # 最多补充 3 个查询，避免爆炸

    def run_validator(self, user_input: str, architect_data: dict, researcher_result: dict) -> str:
        """
        Phase 3: Validation & Protocol Generation with RAG (raw chunks exposed).
        """
        synthesis = researcher_result.get("synthesis", "")
        raw_chunks: List[EvidenceChunk] = researcher_result.get("chunks", [])

        raw_corpus_text = "\n".join([c.to_text() for c in raw_chunks]) if raw_chunks else "(无原始证据)"

        prompt = (
            f"User Intent: {user_input}\n\n"
            f"Architect Needs:\n{json.dumps(architect_data, ensure_ascii=False, indent=2)}\n\n"
            f"Researcher Synthesis:\n{synthesis}\n\n"
            f"--- RAW EVIDENCE CORPUS ---\n{raw_corpus_text}\n"
        )

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        report = response.choices[0].message.content

        # 轻量级输出校验 / 清洗
        report = self._sanitize_validator_output(report)
        return report

    @staticmethod
    def _sanitize_validator_output(report: str) -> str:
        """
        轻量级输出校验：
        1. 确保有必要的章节标题（没有则补占位符）
        2. 对 Mermaid 代码块做简单清理（替换可能破坏语法的中文冒号、括号）
        """
        required_sections = [
            ("# 📊 协议流程概览", "# 📊 协议流程概览 (Flowchart)\n\n```mermaid\ngraph TD\n    A[开始] --> B[步骤1]\n```\n"),
            ("# 确切实验步骤", "# 确切实验步骤 / 执行方案\n\n（无详细步骤）\n"),
            ("# 📦 试剂与耗材采购清单", "# 📦 试剂与耗材采购清单\n\n| 物品名称 (Item) | 规格/用量 (Quantity) | 用途 (Purpose) |\n|---|---|---|\n| 待定 | 待定 | 待定 |\n"),
            ("# 证据溯源链接", "# 证据溯源链接\n\n- 无可用外部链接\n"),
        ]

        for marker, fallback in required_sections:
            if marker not in report:
                report += f"\n\n{fallback}"

        # 简单清理 Mermaid 代码块中的危险字符
        def _fix_mermaid(m):
            code = m.group(1)
            # Mermaid 节点 ID 和文本中常见破坏字符
            code = code.replace("（", "(").replace("）", ")")
            code = code.replace("：", ":")
            code = code.replace("，", ",")
            # 避免空节点定义
            code = re.sub(r"\b(\w+)\s*\[\s*\]", r"\1[未命名节点]", code)
            return f"```mermaid\n{code}\n```"

        report = re.sub(r"```mermaid\n([\s\S]*?)\n```", _fix_mermaid, report)
        return report
