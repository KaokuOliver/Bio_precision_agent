from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from .config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_DEFAULT_MODEL,
    DEEPSEEK_DEFAULT_THINKING,
    DEEPSEEK_LEGACY_MODEL_ALIASES,
)
from .prompts import ARCHITECT_PROMPT, RESEARCHER_PROMPT, VALIDATOR_PROMPT
from .researcher import CitationVerifier, EvidenceChunk, get_duckduckgo_search_results, fetch_pubmed_abstracts, orchestrate_research


def normalize_deepseek_model(model_name: str, thinking_mode: Optional[str] = None) -> Tuple[str, str]:
    requested_model = (model_name or DEEPSEEK_DEFAULT_MODEL).strip()
    if requested_model in DEEPSEEK_LEGACY_MODEL_ALIASES:
        mapped_model, inferred_thinking = DEEPSEEK_LEGACY_MODEL_ALIASES[requested_model]
        return mapped_model, thinking_mode or inferred_thinking
    return requested_model, thinking_mode or DEEPSEEK_DEFAULT_THINKING


class ArchitectOutput(BaseModel):
    Experiment_Type: str = Field(description="'wet', 'dry', or 'mixed'")
    Species: str = Field(description="Target organism species")
    Key_Goal: str = Field(description="The core scientific objective")
    Params: List[str] = Field(description="Concrete evidence questions")

    @classmethod
    def validate_and_clean(cls, raw_data: dict) -> dict:
        data = dict(raw_data)
        experiment_type = str(data.get("Experiment_Type", "mixed")).lower().strip()
        data["Experiment_Type"] = experiment_type if experiment_type in {"wet", "dry", "mixed"} else "mixed"

        params = data.get("Params", [])
        if isinstance(params, str):
            params = [params]
        if not isinstance(params, list):
            params = []
        data["Params"] = [
            str(param).strip()
            for param in params
            if str(param).strip() and str(param).strip().lower() not in {"none", "null", "nan"}
        ]

        for key in ("Species", "Key_Goal"):
            data[key] = str(data.get(key) or "").strip()
        return data


class BioPrecisionAgents:
    def __init__(
        self,
        api_key: str,
        model_name: str = DEEPSEEK_DEFAULT_MODEL,
        thinking_mode: Optional[str] = None,
    ):
        self.client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        self.model_name, self.thinking_mode = normalize_deepseek_model(model_name, thinking_mode)

    def _create_chat_completion(self, **kwargs):
        extra_body = kwargs.pop("extra_body", {}) or {}
        extra_body.setdefault("thinking", {"type": self.thinking_mode})
        if self.thinking_mode == "enabled":
            extra_body.setdefault("reasoning_effort", "high")
        return self.client.chat.completions.create(**kwargs, extra_body=extra_body)

    def run_architect(self, user_input: str, pdf_text: str = "") -> dict:
        pdf_context = f"\n\n--- Uploaded PDF Context ---\n{pdf_text[:8000]}" if pdf_text else ""
        prompt = (
            f"User intent: {user_input}{pdf_context}\n\n"
            "Return only JSON with this schema: "
            "{'Experiment_Type': str, 'Species': str, 'Key_Goal': str, 'Params': [str, ...]}"
        )
        response = self._create_chat_completion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": ARCHITECT_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        try:
            data = json.loads(response.choices[0].message.content.strip())
            cleaned = ArchitectOutput.validate_and_clean(data)
            return ArchitectOutput.model_validate(cleaned).model_dump()
        except (json.JSONDecodeError, ValidationError) as exc:
            raw = response.choices[0].message.content
            raise ValueError(f"Architect parsing failed: {exc}\nRaw response: {raw}") from exc

    def run_researcher(self, user_input: str, architect_data: dict, pdf_text: str = "") -> dict:
        species = architect_data.get("Species", "")
        key_goal = architect_data.get("Key_Goal", "")
        params = architect_data.get("Params", [])

        research_result = orchestrate_research(params, species, key_goal, pdf_text)
        chunks: List[EvidenceChunk] = research_result["chunks"]
        citations = research_result.get("citations", [])
        synthesis = self._call_researcher_synthesizer(user_input, params, research_result["summary_text"])

        follow_up_queries = self._extract_follow_up_queries(synthesis)
        if follow_up_queries:
            supplemental: List[EvidenceChunk] = []
            for query in follow_up_queries:
                pubmed_chunks, pubmed_citations = fetch_pubmed_abstracts(query, max_results=2)
                supplemental.extend(pubmed_chunks)
                citations.extend(pubmed_citations)
                supplemental.extend(get_duckduckgo_search_results(query, max_results=2))
            if supplemental:
                from .researcher import _deduplicate_chunks, _truncate_chunks

                chunks = _truncate_chunks(_deduplicate_chunks([*chunks, *supplemental]))
                synthesis = self._call_researcher_synthesizer(
                    user_input,
                    params,
                    "\n".join(chunk.to_text() for chunk in chunks),
                )

        return {"synthesis": synthesis, "chunks": chunks, "citations": citations}

    def _call_researcher_synthesizer(self, user_input: str, params: List[str], evidence_text: str) -> str:
        prompt = (
            f"User intent: {user_input}\n"
            f"Parameters to resolve: {params}\n\n"
            f"Evidence corpus:\n{evidence_text}\n\n"
            "Synthesize the corpus according to the system instructions."
        )
        response = self._create_chat_completion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": RESEARCHER_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

    @staticmethod
    def _extract_follow_up_queries(text: str) -> List[str]:
        match = re.search(r"FOLLOW_UP_QUERIES:(.*?)(?:\n# |\n---|\Z)", text, re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        queries = []
        for line in match.group(1).strip().splitlines():
            query = re.sub(r"^[\-\*\d]+[\.\)]\s*", "", line.strip())
            if len(query) > 5:
                queries.append(query)
        return queries[:3]

    def run_validator(self, user_input: str, architect_data: dict, researcher_result: dict) -> str:
        chunks: List[EvidenceChunk] = researcher_result.get("chunks", [])
        citations = researcher_result.get("citations", [])
        raw_corpus = "\n".join(chunk.to_text() for chunk in chunks) if chunks else "(No raw evidence available.)"
        audit = CitationVerifier(chunks, citations).audit_markdown(researcher_result.get("synthesis", ""))
        prompt = (
            f"User intent:\n{user_input}\n\n"
            f"Architect requirements:\n{json.dumps(architect_data, ensure_ascii=False, indent=2)}\n\n"
            f"Researcher synthesis:\n{researcher_result.get('synthesis', '')}\n\n"
            f"Citation audit:\n{json.dumps(audit, ensure_ascii=False, indent=2)}\n\n"
            f"--- Raw Evidence Corpus ---\n{raw_corpus}\n"
        )
        response = self._create_chat_completion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        report = self._sanitize_validator_output(response.choices[0].message.content)
        final_audit = CitationVerifier(chunks, citations).audit_markdown(report)
        if final_audit["unknown_pmids"] or final_audit["unknown_urls"]:
            report += "\n\n# Citation Audit Notes\n"
            if final_audit["unknown_pmids"]:
                report += f"- Unknown PMIDs removed or require manual verification: {', '.join(final_audit['unknown_pmids'])}\n"
            if final_audit["unknown_urls"]:
                report += "- URLs requiring manual verification:\n"
                for url in final_audit["unknown_urls"][:10]:
                    report += f"  - {url}\n"
        return report

    @staticmethod
    def _sanitize_validator_output(report: str) -> str:
        required_sections = [
            ("# Protocol Flowchart", "# Protocol Flowchart\n\n```mermaid\ngraph TD\n    A[Start] --> B[Review evidence]\n```\n"),
            ("# Exact Experimental Steps / Execution Plan", "# Exact Experimental Steps / Execution Plan\n\n**[UNVERIFIED - manual lookup required]**\n"),
            ("# Reagents, Consumables, and Compute Bill of Materials", "# Reagents, Consumables, and Compute Bill of Materials\n\n| Item | Specification / Quantity | Purpose |\n|---|---|---|\n| N/A | N/A | N/A |\n"),
            ("# Evidence Traceability", "# Evidence Traceability\n\n- No traceable external source was available.\n"),
        ]
        for marker, fallback in required_sections:
            if marker not in report:
                report += f"\n\n{fallback}"

        def fix_mermaid(match):
            code = match.group(1)
            code = code.replace("：", ":").replace("，", ",").replace("（", "(").replace("）", ")")
            code = re.sub(r"\b(\w+)\s*\[\s*\]", r"\1[Unnamed node]", code)
            return f"```mermaid\n{code.strip()}\n```"

        return re.sub(r"```mermaid\n([\s\S]*?)\n```", fix_mermaid, report)
