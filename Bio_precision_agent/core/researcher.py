import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from Bio import Entrez
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import hashlib
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 告诉 NCBI 我们是谁 (遵守其访问协议)
Entrez.email = "researcher@bio-precision-agent.local"


@dataclass
class EvidenceChunk:
    """结构化证据片段，保留溯源信息，用于 RAG 架构。"""
    source_type: str  # "pubmed", "web", "pdf"
    query: str        # 检索该片段时使用的查询词
    content: str
    source_id: str = ""     # PMID 或 URL
    source_title: str = ""
    rank: int = 0           # 在检索结果中的排序

    def to_text(self) -> str:
        header = f"[{self.source_type.upper()}]"
        if self.source_id:
            header += f" {self.source_id}"
        if self.source_title:
            header += f" | {self.source_title}"
        return f"{header}\nQuery: {self.query}\n{self.content}\n"


@dataclass
class CitationRecord:
    """用于验证引用真实性的记录。"""
    source_type: str
    source_id: str
    content_hash: str = ""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text[:200].encode("utf-8")).hexdigest()[:16]


def fetch_pubmed_abstracts(query: str, max_results: int = 3) -> Tuple[List[EvidenceChunk], List[CitationRecord]]:
    """
    使用 BioPython 调用 NCBI 官方 PubMed API。
    返回结构化的 EvidenceChunk 列表和可验证的 CitationRecord 列表。
    """
    chunks: List[EvidenceChunk] = []
    citations: List[CitationRecord] = []

    try:
        logger.info(f"Querying PubMed: {query}")
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()

        id_list = record.get("IdList", [])
        if not id_list:
            logger.info(f"No PubMed results for: {query}")
            return chunks, citations

        # 批量获取摘要
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), rettype="medline", retmode="text")
        medline_data = fetch_handle.read()
        fetch_handle.close()

        # 简单按记录分割（Medline 记录之间以空行分隔，但这里按 PMID 拆更稳）
        for pmid in id_list:
            # 提取该 PMID 对应的片段（简单做法：找 PM  -  {pmid} 的位置）
            marker = f"PMID- {pmid}"
            idx = medline_data.find(marker)
            if idx == -1:
                continue
            start = idx
            end = medline_data.find("PMID- ", idx + len(marker))
            if end == -1:
                record_text = medline_data[start:]
            else:
                record_text = medline_data[start:end]

            record_text = record_text.strip()
            if not record_text:
                continue

            chunk = EvidenceChunk(
                source_type="pubmed",
                query=query,
                content=record_text[:4000],
                source_id=pmid,
                source_title=f"PubMed PMID:{pmid}"
            )
            chunks.append(chunk)
            citations.append(CitationRecord(
                source_type="pubmed",
                source_id=pmid,
                content_hash=_content_hash(record_text)
            ))

        return chunks, citations
    except Exception as e:
        logger.warning(f"PubMed fetch failed: {e}")
        return chunks, citations


def fetch_webpage_content(url: str, max_length: int = 4000, retries: int = 2) -> str:
    """
    深度抓取网页的文字内容（脱水处理）。
    增加了重试、更 aggressive 的去噪、简单动态渲染检测。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    last_err = ""
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            break
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Web fetch attempt {attempt + 1} failed for {url}: {e}")
            time.sleep(1)
    else:
        return ""

    try:
        soup = BeautifulSoup(res.content, "html.parser")

        # 如果 body 几乎为空，可能是 JS 渲染页面
        body_text_raw = soup.get_text(strip=True)
        if len(body_text_raw) < 200:
            logger.info(f"Page likely JS-rendered or paywalled, skipping: {url}")
            return ""

        # Aggressive 去噪：移除 script, style, nav, footer, header, aside, advertisement, cookie banners
        for selector in [
            "script", "style", "nav", "footer", "header", "aside",
            "[class*='ad']", "[class*='cookie']", "[class*='popup']",
            "[id*='ad']", "[id*='cookie']", "[id*='popup']"
        ]:
            for el in soup.select(selector):
                el.extract()

        # 优先提取 article / main / div.content 等核心内容区
        main_content = ""
        for tag in ["article", "main", "[role='main']"]:
            el = soup.select_one(tag)
            if el:
                main_content = el.get_text(separator=" ", strip=True)
                break

        if not main_content:
            main_content = soup.get_text(separator=" ", strip=True)

        text = " ".join(main_content.split())

        if len(text) > max_length:
            return text[:max_length] + "...[截断]"
        return text
    except Exception as e:
        logger.warning(f"HTML parse failed for {url}: {e}")
        return ""


def get_duckduckgo_search_results(query: str, max_results: int = 2) -> List[EvidenceChunk]:
    """
    使用 DuckDuckGo API 检索泛型信息辅助 NCBI。
    返回 EvidenceChunk 列表，失败返回空列表。
    """
    chunks: List[EvidenceChunk] = []
    try:
        results = DDGS().text(query, max_results=max_results)
        seen_urls: set = set()
        for i, res in enumerate(results):
            title = res.get("title", "No Title")
            href = res.get("href", "")
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            body_snippet = res.get("body", "")
            full_text = fetch_webpage_content(href)
            content_to_use = full_text if len(full_text) > 200 else body_snippet

            if not content_to_use or len(content_to_use) < 50:
                continue

            chunks.append(EvidenceChunk(
                source_type="web",
                query=query,
                content=content_to_use[:4000],
                source_id=href,
                source_title=title,
                rank=i + 1
            ))
        return chunks
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return chunks


def _deduplicate_chunks(chunks: List[EvidenceChunk]) -> List[EvidenceChunk]:
    """基于内容哈希的简单去重。"""
    seen: set = set()
    out: List[EvidenceChunk] = []
    for c in chunks:
        h = _content_hash(c.content)
        if h not in seen:
            seen.add(h)
            out.append(c)
    return out


def orchestrate_research(params_list: list, species: str, key_goal: str, pdf_text: str = "") -> Dict:
    """
    核心升级：融合 NCBI 专业库与外网 Deep Scraping。
    返回结构化字典，包含：
    - chunks: List[EvidenceChunk] 原始证据片段（用于 Validator 直接核对）
    - citations: List[CitationRecord] 可验证引用记录
    - summary_text: str 给 Researcher (Synthesizer) 阅读的摘要文本
    """
    all_chunks: List[EvidenceChunk] = []
    all_citations: List[CitationRecord] = []

    # 1. 处理上传的 PDF（金标准）
    if pdf_text and len(pdf_text.strip()) > 50:
        # 对 PDF 做简单语义分块：优先保留含有关键词的段落
        pdf_chunks = _chunk_pdf_text(pdf_text, species, params_list)
        for i, pc in enumerate(pdf_chunks):
            all_chunks.append(EvidenceChunk(
                source_type="pdf",
                query="uploaded_pdf",
                content=pc[:4000],
                source_id="uploaded_pdf",
                source_title="用户上传 PDF",
                rank=i + 1
            ))

    # 2. 针对核心主题的整体检索
    pubmed_query = f"{species} {key_goal}"
    pub_chunks, pub_cits = fetch_pubmed_abstracts(pubmed_query, max_results=3)
    all_chunks.extend(pub_chunks)
    all_citations.extend(pub_cits)

    web_query = f"{species} {key_goal} protocol methods"
    web_chunks = get_duckduckgo_search_results(web_query, max_results=2)
    all_chunks.extend(web_chunks)

    # 3. 针对每个具体参数的检索（不再截断到前3个）
    for param in params_list:
        param = str(param).strip()
        if not param:
            continue
        p_chunks, p_cits = fetch_pubmed_abstracts(f"{species} {param}", max_results=2)
        all_chunks.extend(p_chunks)
        all_citations.extend(p_cits)

        w_chunks = get_duckduckgo_search_results(f"{species} {param} parameter protocols", max_results=2)
        all_chunks.extend(w_chunks)

    # 去重
    all_chunks = _deduplicate_chunks(all_chunks)

    # 4. 智能截断：优先保留完整块，而不是直接砍字符串
    final_chunks = _truncate_chunks(all_chunks, max_total_chars=22000)

    # 生成 Researcher 可读的摘要文本
    summary_lines = []
    for c in final_chunks:
        summary_lines.append(c.to_text())
    summary_text = "\n".join(summary_lines)

    return {
        "chunks": final_chunks,
        "citations": all_citations,
        "summary_text": summary_text,
    }


def _chunk_pdf_text(text: str, species: str, params_list: List[str]) -> List[str]:
    """
    对 PDF 文本做简单语义分块：
    1. 按段落分割
    2. 给每段打分（是否包含物种名、参数关键词、方法学关键词）
    3. 优先返回高分段落，限制总长度
    """
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 10]
    if not paragraphs:
        return [text[:12000]]

    keywords = set([species.lower()] + [p.lower() for p in params_list if p])
    method_keywords = {"method", "protocol", "concentration", "temperature", "pcr", "rna", "dna", "buffer", "reagent"}

    scored = []
    for p in paragraphs:
        p_lower = p.lower()
        score = 0
        for kw in keywords:
            if kw in p_lower:
                score += 2
        for mkw in method_keywords:
            if mkw in p_lower:
                score += 1
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 保留高分段落，同时保留前 3 个原始顺序段落（防止目录/封面后全是高分段导致顺序混乱）
    selected = []
    total_len = 0
    max_len = 12000

    # 先加前3个原始段落（通常是标题/摘要）
    for p in paragraphs[:3]:
        if total_len + len(p) > max_len:
            break
        selected.append(p)
        total_len += len(p)

    # 再加高分段落
    for _, p in scored:
        if p in selected:
            continue
        if total_len + len(p) > max_len:
            break
        selected.append(p)
        total_len += len(p)

    return selected


def _truncate_chunks(chunks: List[EvidenceChunk], max_total_chars: int = 22000) -> List[EvidenceChunk]:
    """
    按块截断：优先保留完整块。若某个块会导致超限时，尝试只保留其一半，
    若仍超限则丢弃后续块。
    """
    result: List[EvidenceChunk] = []
    current_len = 0
    for c in chunks:
        needed = len(c.to_text())
        if current_len + needed <= max_total_chars:
            result.append(c)
            current_len += needed
        else:
            # 尝试截断当前块的一半
            remaining = max_total_chars - current_len
            if remaining > 500:
                half_content = c.content[: remaining - 100]
                result.append(EvidenceChunk(
                    source_type=c.source_type,
                    query=c.query,
                    content=half_content + "...[截断]",
                    source_id=c.source_id,
                    source_title=c.source_title,
                    rank=c.rank
                ))
            break
    return result


class CitationVerifier:
    """
    验证 Researcher 输出的引用是否真实存在于检索结果中。
    """
    def __init__(self, citations: List[CitationRecord]):
        self._index: Dict[str, CitationRecord] = {}
        for c in citations:
            key = f"{c.source_type}:{c.source_id}"
            self._index[key] = c

    def verify(self, cited_source_type: str, cited_id: str) -> bool:
        key = f"{cited_source_type}:{cited_id}"
        return key in self._index

    def get_valid_sources(self) -> List[str]:
        return [f"{c.source_type}:{c.source_id}" for c in self._index.values()]
