from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import requests
from Bio import Entrez
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from .config import CACHE_DIR, CACHE_TTL_SECONDS, MAX_EVIDENCE_CHARS, NCBI_EMAIL, WEB_TIMEOUT_SECONDS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
Entrez.email = NCBI_EMAIL

TRUSTED_WEB_HINTS = (
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "nature.com",
    "science.org",
    "cell.com",
    "springer.com",
    "wiley.com",
    "frontiersin.org",
    "plos.org",
    "biorxiv.org",
    "protocols.io",
    "rdocumentation.org",
    "bioconductor.org",
    "cran.r-project.org",
)


@dataclass
class EvidenceChunk:
    source_type: str
    query: str
    content: str
    source_id: str = ""
    source_title: str = ""
    rank: int = 0
    year: str = ""
    url: str = ""
    trust_score: int = 0

    def to_text(self) -> str:
        label = f"[{self.source_type.upper()}]"
        source = self.source_id or self.url
        if source:
            label += f" {source}"
        if self.source_title:
            label += f" | {self.source_title}"
        if self.year:
            label += f" | {self.year}"
        return (
            f"{label}\n"
            f"Query: {self.query}\n"
            f"Trust score: {self.trust_score}\n"
            f"{self.content}\n"
        )


@dataclass
class CitationRecord:
    source_type: str
    source_id: str
    source_title: str = ""
    url: str = ""
    year: str = ""
    content_hash: str = ""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text[:500].encode("utf-8", errors="ignore")).hexdigest()[:16]


def _cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(f"{namespace}:{key}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{namespace}_{digest}.json"


def _read_cache(namespace: str, key: str):
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - payload.get("created_at", 0) > CACHE_TTL_SECONDS:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_cache(namespace: str, key: str, data) -> None:
    path = _cache_path(namespace, key)
    payload = {"created_at": time.time(), "data": data}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _rank_url(url: str) -> int:
    host = urlparse(url).netloc.lower()
    score = 1
    for hint in TRUSTED_WEB_HINTS:
        if hint in host:
            score += 3
            break
    if any(word in host for word in ("forum", "reddit", "medium", "blog")):
        score -= 1
    return max(score, 0)


def _article_year(article: dict) -> str:
    journal = article.get("Journal", {})
    issue = journal.get("JournalIssue", {})
    pub_date = issue.get("PubDate", {})
    return str(pub_date.get("Year") or pub_date.get("MedlineDate") or "")


def _article_title(article: dict) -> str:
    title = article.get("ArticleTitle", "")
    return str(title).strip()


def _abstract_text(article: dict) -> str:
    abstract = article.get("Abstract", {})
    parts = abstract.get("AbstractText", [])
    if isinstance(parts, str):
        return parts
    return " ".join(str(part) for part in parts)


def fetch_pubmed_abstracts(query: str, max_results: int = 3) -> Tuple[List[EvidenceChunk], List[CitationRecord]]:
    chunks: List[EvidenceChunk] = []
    citations: List[CitationRecord] = []
    cache_key = f"{query}|{max_results}"
    cached = _read_cache("pubmed", cache_key)
    if cached:
        return (
            [EvidenceChunk(**item) for item in cached.get("chunks", [])],
            [CitationRecord(**item) for item in cached.get("citations", [])],
        )

    try:
        logger.info("Querying PubMed: %s", query)
        search_handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
        search_record = Entrez.read(search_handle)
        search_handle.close()
        pmids = list(search_record.get("IdList", []))
        if not pmids:
            return chunks, citations

        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(pmids), retmode="xml")
        records = Entrez.read(fetch_handle)
        fetch_handle.close()

        for rank, entry in enumerate(records.get("PubmedArticle", []), start=1):
            medline = entry.get("MedlineCitation", {})
            pmid = str(medline.get("PMID", ""))
            article = medline.get("Article", {})
            title = _article_title(article)
            year = _article_year(article)
            abstract = _abstract_text(article)
            if not abstract:
                abstract = title
            journal = article.get("Journal", {}).get("Title", "")
            content = f"Title: {title}\nJournal: {journal}\nYear: {year}\nAbstract: {abstract}".strip()
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            chunk = EvidenceChunk(
                source_type="pubmed",
                query=query,
                content=content[:4500],
                source_id=pmid,
                source_title=title or f"PubMed PMID:{pmid}",
                rank=rank,
                year=year,
                url=url,
                trust_score=5,
            )
            chunks.append(chunk)
            citations.append(
                CitationRecord(
                    source_type="pubmed",
                    source_id=pmid,
                    source_title=chunk.source_title,
                    url=url,
                    year=year,
                    content_hash=_content_hash(content),
                )
            )
    except Exception as exc:
        logger.warning("PubMed fetch failed for %s: %s", query, exc)

    _write_cache("pubmed", cache_key, {
        "chunks": [asdict(item) for item in chunks],
        "citations": [asdict(item) for item in citations],
    })
    return chunks, citations


def fetch_webpage_content(url: str, max_length: int = 4000, retries: int = 2) -> str:
    cached = _read_cache("webpage", url)
    if cached is not None:
        return cached

    headers = {
        "User-Agent": "Bio-Precision-Agent/5.0 (+https://github.com/)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=WEB_TIMEOUT_SECONDS)
            response.raise_for_status()
            break
        except Exception as exc:
            logger.warning("Web fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
            time.sleep(0.8)
    if response is None:
        return ""

    try:
        soup = BeautifulSoup(response.content, "html.parser")
        if len(soup.get_text(strip=True)) < 200:
            return ""
        for selector in [
            "script", "style", "nav", "footer", "header", "aside",
            "[class*='ad']", "[class*='cookie']", "[class*='popup']",
            "[id*='ad']", "[id*='cookie']", "[id*='popup']",
        ]:
            for element in soup.select(selector):
                element.extract()
        main = soup.select_one("article") or soup.select_one("main") or soup.select_one("[role='main']")
        text = (main or soup).get_text(separator=" ", strip=True)
        text = " ".join(text.split())
        text = text[:max_length] + ("...[truncated]" if len(text) > max_length else "")
        _write_cache("webpage", url, text)
        return text
    except Exception as exc:
        logger.warning("HTML parse failed for %s: %s", url, exc)
        return ""


def get_duckduckgo_search_results(query: str, max_results: int = 2) -> List[EvidenceChunk]:
    cache_key = f"{query}|{max_results}"
    cached = _read_cache("ddg", cache_key)
    if cached:
        return [EvidenceChunk(**item) for item in cached]

    chunks: List[EvidenceChunk] = []
    try:
        seen_urls: set[str] = set()
        for rank, result in enumerate(DDGS().text(query, max_results=max_results), start=1):
            url = result.get("href", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = result.get("title", "Untitled source")
            snippet = result.get("body", "")
            full_text = fetch_webpage_content(url)
            content = full_text if len(full_text) > 200 else snippet
            if len(content) < 50:
                continue
            chunks.append(
                EvidenceChunk(
                    source_type="web",
                    query=query,
                    content=content[:4000],
                    source_id=url,
                    source_title=title,
                    rank=rank,
                    url=url,
                    trust_score=_rank_url(url),
                )
            )
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for %s: %s", query, exc)

    chunks.sort(key=lambda item: item.trust_score, reverse=True)
    _write_cache("ddg", cache_key, [asdict(item) for item in chunks])
    return chunks


def _deduplicate_chunks(chunks: Iterable[EvidenceChunk]) -> List[EvidenceChunk]:
    seen: set[str] = set()
    unique: List[EvidenceChunk] = []
    for chunk in chunks:
        source_key = f"{chunk.source_type}:{chunk.source_id or chunk.url}"
        text_key = _content_hash(chunk.content)
        key = source_key if source_key != f"{chunk.source_type}:" else text_key
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def _truncate_chunks(chunks: List[EvidenceChunk], max_total_chars: int = MAX_EVIDENCE_CHARS) -> List[EvidenceChunk]:
    output: List[EvidenceChunk] = []
    current_len = 0
    for chunk in chunks:
        rendered = chunk.to_text()
        if current_len + len(rendered) <= max_total_chars:
            output.append(chunk)
            current_len += len(rendered)
            continue
        remaining = max_total_chars - current_len
        if remaining > 700:
            output.append(
                EvidenceChunk(
                    source_type=chunk.source_type,
                    query=chunk.query,
                    content=chunk.content[: remaining - 180] + "...[truncated]",
                    source_id=chunk.source_id,
                    source_title=chunk.source_title,
                    rank=chunk.rank,
                    year=chunk.year,
                    url=chunk.url,
                    trust_score=chunk.trust_score,
                )
            )
        break
    return output


def _chunk_pdf_text(text: str, species: str, params_list: List[str]) -> List[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if len(item.strip()) > 30]
    if not paragraphs:
        return [text[:12000]]
    keywords = {species.lower(), "method", "protocol", "concentration", "temperature", "pcr", "rna", "dna", "buffer"}
    keywords.update(str(param).lower() for param in params_list if param)

    scored = []
    for index, paragraph in enumerate(paragraphs):
        lower = paragraph.lower()
        score = sum(2 for keyword in keywords if keyword and keyword in lower)
        score += 1 if index < 3 else 0
        scored.append((score, index, paragraph))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: List[str] = []
    total = 0
    for _, _, paragraph in scored:
        if total + len(paragraph) > 12000:
            continue
        selected.append(paragraph)
        total += len(paragraph)
        if total >= 10000:
            break
    return selected or [text[:12000]]


def orchestrate_research(params_list: list, species: str, key_goal: str, pdf_text: str = "") -> Dict:
    all_chunks: List[EvidenceChunk] = []
    all_citations: List[CitationRecord] = []

    if pdf_text and len(pdf_text.strip()) > 50:
        for rank, content in enumerate(_chunk_pdf_text(pdf_text, species, params_list), start=1):
            all_chunks.append(
                EvidenceChunk(
                    source_type="pdf",
                    query="uploaded_pdf",
                    content=content[:4500],
                    source_id=f"uploaded_pdf:{rank}",
                    source_title="User uploaded PDF",
                    rank=rank,
                    trust_score=6,
                )
            )

    query_plan = [f"{species} {key_goal}".strip()]
    query_plan.extend(f"{species} {param}".strip() for param in params_list if str(param).strip())

    for query in query_plan:
        pub_chunks, pub_citations = fetch_pubmed_abstracts(query, max_results=3)
        all_chunks.extend(pub_chunks)
        all_citations.extend(pub_citations)
        all_chunks.extend(get_duckduckgo_search_results(f"{query} protocol methods", max_results=2))

    all_chunks = _deduplicate_chunks(all_chunks)
    all_chunks.sort(key=lambda item: (item.trust_score, -item.rank), reverse=True)
    final_chunks = _truncate_chunks(all_chunks)

    return {
        "chunks": final_chunks,
        "citations": all_citations,
        "summary_text": "\n".join(chunk.to_text() for chunk in final_chunks),
    }


class CitationVerifier:
    def __init__(self, chunks: List[EvidenceChunk], citations: List[CitationRecord] | None = None):
        self._valid_pmids = {chunk.source_id for chunk in chunks if chunk.source_type == "pubmed" and chunk.source_id}
        self._valid_urls = {chunk.url or chunk.source_id for chunk in chunks if chunk.source_type == "web"}
        if citations:
            self._valid_pmids.update(item.source_id for item in citations if item.source_type == "pubmed")

    def audit_markdown(self, markdown: str) -> Dict[str, List[str]]:
        cited_pmids = set(re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)|PMID[:\s]*(\d+)", markdown, re.I))
        cited_pmids = {left or right for left, right in cited_pmids}
        cited_urls = set(re.findall(r"https?://[^\s)\]>]+", markdown))
        return {
            "unknown_pmids": sorted(pmid for pmid in cited_pmids if pmid not in self._valid_pmids),
            "unknown_urls": sorted(url for url in cited_urls if url not in self._valid_urls and "pubmed.ncbi.nlm.nih.gov" not in url),
            "valid_pmids": sorted(self._valid_pmids),
            "valid_urls": sorted(self._valid_urls),
        }
