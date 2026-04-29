# Bio-Precision Agent V5

Evidence-grounded biomedical protocol generation with multi-agent reasoning, PubMed retrieval, web evidence collection, uploaded PDF context, and citation auditing.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-red.svg)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-green.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

## What It Does

Bio-Precision Agent V5 turns a biomedical research goal into a traceable protocol. It does not simply ask an LLM for plausible values. Instead, it parses the task, retrieves evidence, synthesizes only what appears in the evidence corpus, validates citations, and marks unsupported claims as `UNVERIFIED`.

The intended use cases include wet-lab protocol planning, dry-lab workflow generation, mixed experimental design, literature-backed parameter discovery, and reproducible analysis notebook generation.

## Workflow

```text
User research goal
        |
        v
Architect Agent
  - Extracts species, experiment type, objective, and evidence questions
  - Validates JSON with Pydantic
        |
        v
Human confirmation
  - User edits the structured plan before retrieval
        |
        v
Researcher Agent
  - Retrieves PubMed XML records
  - Searches selected web sources
  - Scores and deduplicates evidence chunks
  - Adds uploaded PDF context when available
        |
        v
Validator Agent
  - Checks raw evidence against synthesized claims
  - Audits citations
  - Generates a Markdown protocol, BOM, and traceability section
```

## Key Improvements in V5

- DeepSeek V4 Flash is the default model.
- Legacy `deepseek-chat` and `deepseek-reasoner` aliases are mapped to V4 Flash compatibility modes.
- DeepSeek thinking mode is explicitly configurable and defaults to off for faster runs.
- PubMed retrieval now uses structured XML instead of fragile text splitting.
- Evidence chunks include title, year, URL, source type, rank, and trust score.
- PubMed, DuckDuckGo, and webpage fetches use a local JSON cache.
- Validator prompts receive a citation audit and are instructed not to use unknown PMIDs or URLs.
- Streamlit report rendering no longer enables unsafe HTML for LLM-generated Markdown.
- The full UI, prompts, comments, CLI, and documentation are now English.
- The new V5 directory is independent and does not overwrite V4.

## Project Structure

```text
Bio_precision_agent_V5/
├── app.py                  # Streamlit application
├── auth.py                 # Demo login module
├── main.py                 # CLI smoke-test workflow
├── requirements.txt        # Python dependencies
├── Start_BPA_V5.bat        # Windows launcher
├── README.md
├── CHANGELOG_V5.md
└── core/
    ├── agents.py           # Architect, Researcher, Validator orchestration
    ├── config.py           # Runtime paths and DeepSeek settings
    ├── prompts.py          # English system prompts
    └── researcher.py       # PubMed, web, PDF evidence, caching, citation audit
```

## Requirements

- Python 3.10 or 3.11 recommended
- DeepSeek API key
- Internet access for PubMed and web retrieval

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create or edit `.env`:

```env
DEEPSEEK_API_KEY=sk-your-key
NCBI_EMAIL=your-email@example.com
```

NCBI recommends identifying API clients with a real email address.

## Run the App

Windows:

```powershell
Start_BPA_V5.bat
```

Cross-platform:

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Open:

```text
http://localhost:8501
```

Default local demo login:

```text
Username: admin
Password: admin
```

Change the default credentials before deploying beyond a local machine.

## CLI Demo

```bash
python main.py
```

The CLI writes `bpa_v5_cli_report.md` after completing the three-stage workflow.

## Evidence Policy

V5 follows a conservative evidence policy:

1. Direct values require a traceable evidence chunk.
2. Partial evidence is labeled as literature-supported.
3. Missing evidence is labeled `UNVERIFIED - manual lookup required`.
4. PubMed and uploaded PDFs are weighted above general web pages.
5. Citations that do not appear in the retrieved corpus are surfaced in the citation audit notes.

## Security Notes

- `.env`, history, cache files, and generated reports are excluded by `.gitignore`.
- LLM-generated reports are rendered as Markdown without unsafe HTML.
- The bundled login system is for local demos, not production identity management.
- For production deployment, replace `auth.py` with a real identity provider, salted password hashes, HTTPS, and server-side secret management.

## License

MIT License.
