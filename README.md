# Company Research Agent

An AI-powered pipeline that collects open-source company data from GitHub, analyses each company with a large language model, stores enriched results in SQLite, and exposes everything through a FastAPI REST API and an MCP server — buildable and iterable entirely from the terminal using Claude Code.

---

## Table of Contents

1. [Live Demo](#live-demo)
2. [Architecture Overview](#architecture-overview)
3. [Quick Start](#quick-start)
4. [Environment Variables](#environment-variables)
5. [Running the System](#running-the-system)
6. [API Reference](#api-reference)
7. [MCP Server](#mcp-server)
8. [How the AI Agent Works](#how-the-ai-agent-works)
9. [Database Schema](#database-schema)
10. [Project Structure](#project-structure)
11. [Design Decisions & Assumptions](#design-decisions--assumptions)
12. [Agentic Tool Usage — Claude Code](#agentic-tool-usage--claude-code)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        pipeline.py                          │
│  Orchestrator — runs Stage 1 then Stage 2 in sequence       │
└────────────────────┬──────────────────────┬─────────────────┘
                     │                      │
          ┌──────────▼──────────┐  ┌────────▼────────────────┐
          │     collect.py      │  │       agent.py           │
          │                     │  │                          │
          │  1. Fetch dataset   │  │  1. Load unanalyzed      │
          │     (yc-oss JSON)   │  │     companies from DB    │
          │  2. Enrich via      │  │  2. Check raw_response   │
          │     GitHub API      │  │     cache — skip if hit  │
          │  3. Fetch README    │  │  3. Call OpenRouter API  │
          │     excerpts        │  │     (Gemini 2.5 Flash)   │
          │  4. Fallback to     │  │  4. Strip markdown fences│
          │     seed list       │  │  5. Parse JSON → DB      │
          └──────────┬──────────┘  └────────┬─────────────────┘
                     │                      │
          ┌──────────▼──────────────────────▼─────────────────┐
          │                   database.py                       │
          │   ALL SQLite access lives here — nowhere else       │
          │   companies table + analysis table + indexes        │
          └───────────┬──────────────────────────┬─────────────┘
                      │                          │
         ┌────────────▼──────────┐  ┌────────────▼────────────┐
         │        api.py         │  │      mcp_server.py       │
         │  FastAPI REST server  │  │  MCP server (stdio)      │
         │  5 endpoints          │  │  5 tools for AI agents   │
         └───────────────────────┘  └─────────────────────────┘
```

**Data flow in brief:**

1. `collect.py` fetches the [yc-oss open-source companies](https://github.com/yc-oss/open-source-companies) dataset, enriches each entry with live star counts, language, topics, and a stripped README excerpt via the GitHub API, then upserts records into SQLite.
2. `agent.py` picks up every company that has no analysis row yet, builds a structured prompt, calls **Google Gemini 2.5 Flash Lite** via OpenRouter, and writes the parsed JSON back to the `analysis` table.
3. `api.py` exposes the data over HTTP with filtering, pagination, and a protected pipeline trigger endpoint.
4. `mcp_server.py` wraps the same database queries as MCP tools so any MCP-compatible AI agent (including Claude Code itself) can query the data.

---

## Live Demo

The API is deployed and publicly accessible:

| URL | Description |
|-----|-------------|
| http://45.63.56.26:8000/docs | Interactive Swagger UI |
| http://45.63.56.26:8000/companies | List all companies |
| http://45.63.56.26:8000/stats | Aggregate statistics |

### Action in MCP

[Claude MCP Showcase](https://github.com/user-attachments/assets/dce858b1-d34b-4f61-ae0a-13972f521df7)


---

## Quick Start

### Prerequisites

- Python 3.11+
- An [OpenRouter](https://openrouter.ai) API key (free tier covers Gemini Flash Lite)
- Optional: a GitHub personal access token (raises the GitHub API rate limit from 60 → 5 000 req/hr)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/company-research-agent.git
cd company-research-agent

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the env template and fill in your keys
cp .env.example .env
```

---

## Environment Variables

| Variable            | Required | Description                                                         |
|---------------------|----------|---------------------------------------------------------------------|
| `OPENROUTER_API_KEY` | Yes      | Your OpenRouter key — starts with `sk-or-`                         |
| `PIPELINE_SECRET`   | Yes      | Arbitrary secret used to protect `POST /pipeline/run`              |
| `GITHUB_TOKEN`      | No       | GitHub PAT — dramatically raises rate limits during data collection |

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
PIPELINE_SECRET=some-random-string
GITHUB_TOKEN=ghp_optional
```

---

## Running the System

### Step 1 — Run the full pipeline (collect + analyse)

```bash
python src/pipeline.py
```

This will:
- Fetch and enrich company records from the yc-oss dataset
- Call Gemini to analyse each company not yet in the `analysis` table
- Print progress to stdout as it goes

Alternatively, run each stage independently:

```bash
python src/collect.py   # data collection only
python src/agent.py     # AI analysis only
```

### Step 2 — Start the REST API

```bash
uvicorn src.api:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

### Step 3 — Start the MCP server (optional)

```bash
python src/mcp_server.py
```

To wire it into Claude Code's MCP config, add to your `~/.claude/claude_desktop_config.json` (or the project-level `.claude/settings.json`):

```json
{
  "mcpServers": {
    "company-research": {
      "command": "python",
      "args": ["src/mcp_server.py"]
    }
  }
}
```

---

## API Reference

All responses are JSON. The API is self-documenting at `/docs` (Swagger UI) and `/redoc`.

### `GET /companies`

Returns all companies with their AI-generated insights.

**Query parameters:**

| Parameter  | Type    | Description                                    |
|------------|---------|------------------------------------------------|
| `industry` | string  | Filter by industry (case-insensitive)          |
| `model`    | string  | Filter by business model (case-insensitive)    |
| `page`     | integer | Page number (default: 1)                       |
| `per_page` | integer | Results per page (default: 20)                 |

**Example:**

```bash
curl "http://localhost:8000/companies?industry=Developer+Tools&page=1&per_page=5"
```

```json
[
  {
    "id": 1,
    "name": "supabase",
    "website": "https://supabase.com",
    "description": "The open source Firebase alternative",
    "github_url": "https://github.com/supabase/supabase",
    "stars": 73000,
    "language": "TypeScript",
    "topics": "database,backend,postgres,firebase-alternative",
    "industry": "Developer Tools",
    "business_model": "Open Source / SaaS",
    "summary": "Supabase is an open-source Firebase alternative that provides a Postgres database...",
    "use_case": "Backend-as-a-service for developers who need a scalable, SQL-based database.",
    "analyzed_at": "2026-04-07T10:00:00+00:00"
  }
]
```

---

### `GET /companies/{id}`

Returns the full record for one company, including embedded analysis.

```bash
curl http://localhost:8000/companies/1
```

---

### `GET /companies/{id}/analysis`

Returns only the AI-generated analysis fields for a company, plus the raw LLM response.

```bash
curl http://localhost:8000/companies/1/analysis
```

```json
{
  "id": 3,
  "company_id": 1,
  "industry": "Developer Tools",
  "business_model": "Open Source / SaaS",
  "summary": "...",
  "use_case": "...",
  "raw_response": "{\"industry\": \"...\"}",
  "analyzed_at": "2026-04-07T10:00:00+00:00"
}
```

---

### `GET /stats`

Returns aggregate statistics about the dataset.

```bash
curl http://localhost:8000/stats
```

```json
{
  "total_companies": 42,
  "total_analyzed": 42,
  "coverage_pct": 100.0,
  "by_industry": [
    { "industry": "Developer Tools", "count": 18 },
    { "industry": "AI/ML", "count": 12 },
    { "industry": "DevOps", "count": 7 }
  ]
}
```

---

### `POST /pipeline/run`

Re-triggers the full collect → analyse pipeline. Protected by an API key header.

```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "X-API-Key: your-pipeline-secret"
```

```json
{
  "status": "ok",
  "stats": { "total_companies": 42, "total_analyzed": 42, "coverage_pct": 100.0, "by_industry": [...] }
}
```

Returns `401` if the header is missing or incorrect.

---

## MCP Server

The MCP server exposes five tools that any MCP-compatible AI agent can call:

| Tool                      | Arguments                  | Description                                                    |
|---------------------------|----------------------------|----------------------------------------------------------------|
| `search_companies`        | `industry?`, `query?`      | Filter by industry and/or keyword across name/description/summary |
| `get_company`             | `id`                       | Full company record with embedded analysis                     |
| `get_stats`               | —                          | Aggregate counts and industry breakdown                        |
| `search_by_topic`         | `topic`                    | Find companies by GitHub topic tag (e.g. `llm`, `database`)   |
| `get_industry_tech_stack` | `industry`                 | Language breakdown and average stars for an industry           |

**Example — ask Claude Code (with MCP enabled) a natural-language question:**

> "What AI/ML companies are in the database? Show me the top 3 by stars."

Claude Code will call `search_companies(industry="AI/ML")` internally and return a structured answer.

---

## How the AI Agent Works

### Model

**Google Gemini 2.5 Flash Lite** via the [OpenRouter](https://openrouter.ai) API. OpenRouter provides a unified endpoint for dozens of LLMs; swapping models requires only changing the `MODEL` constant in [src/agent.py](src/agent.py).

### Prompt Design

Each company is analysed with a single structured prompt that includes all available context:

```
You are a technology company analyst. Analyze the following GitHub project and classify it.

Project: {name}
Description: {description}
Stars: {stars}
Primary Language: {language}
Topics: {topics}
README (excerpt): {readme_summary}   ← included only when available

Return ONLY a JSON object with exactly these keys:
- "industry": the industry sector (e.g. "Developer Tools", "AI/ML", ...)
- "business_model": how it generates value (e.g. "Open Source Library", "SaaS", ...)
- "summary": 2-3 sentences describing what this project does
- "use_case": the primary problem it solves, in one sentence

Return only the JSON object. No markdown, no explanation.
```

**Why this works well:**
- Providing `stars`, `language`, and `topics` alongside the description gives the model enough signal to classify confidently even when descriptions are brief.
- README excerpts (up to 600 characters, markdown-stripped) add semantic depth for projects with vague one-line descriptions.
- Instructing the model to return *only* a JSON object (no markdown) reduces parse failures. A `_strip_fences()` function handles the rare cases where Gemini still wraps the response in triple-backtick fences.

### Response Caching

Before every LLM call, `agent.py` checks whether the `analysis` table already contains a `raw_response` for that company. If it does, the cached JSON is returned immediately — no API call is made. This means:

- Re-running the pipeline never double-charges for already-analysed companies.
- The `POST /pipeline/run` endpoint is safe to call repeatedly.

### Error Handling

- JSON parse failures are caught per-company; the error is logged and the loop continues.
- Missing fields (`description`, `language`, `topics`) fall back to safe placeholder strings so the prompt is always complete.

---

## Database Schema

SQLite database stored at `data/companies.db`.

```sql
CREATE TABLE companies (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    website        TEXT,
    description    TEXT,
    github_url     TEXT,
    stars          INTEGER,
    language       TEXT,
    topics         TEXT,           -- comma-separated GitHub topic tags
    readme_summary TEXT,           -- first 600 chars of stripped README
    collected_at   TEXT NOT NULL   -- ISO-8601 UTC timestamp
);

CREATE TABLE analysis (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id     INTEGER NOT NULL REFERENCES companies(id),
    industry       TEXT NOT NULL,
    business_model TEXT NOT NULL,
    summary        TEXT NOT NULL,
    use_case       TEXT NOT NULL,
    raw_response   TEXT,           -- full LLM response stored for cache + audit
    analyzed_at    TEXT NOT NULL
);

CREATE INDEX idx_analysis_industry ON analysis(industry);
```

**All SQL lives in `src/database.py`** — no inline queries anywhere else. This is enforced by project convention (see `CLAUDE.md`) and makes the data layer trivially swappable.

The schema is forward-compatible: `init_db()` runs `ALTER TABLE … ADD COLUMN` migrations behind `try/except` so existing databases are upgraded non-destructively on startup.

---

## Project Structure

```
company-research-agent/
├── src/
│   ├── collect.py      # Data collection — GitHub API + seed fallback, idempotent upserts
│   ├── agent.py        # AI analysis — prompt, LLM call, cache check, JSON parse
│   ├── database.py     # All SQLite logic — init, read, write, stats
│   ├── api.py          # FastAPI app — 5 endpoints, API-key protection
│   ├── mcp_server.py   # MCP server — 5 tools wrapping database.py
│   └── pipeline.py     # Orchestrator — runs collect then agent
├── data/
│   └── .gitkeep        # companies.db lives here (git-ignored)
├── .env.example
├── .gitignore
├── requirements.txt
├── CLAUDE.md           # Project conventions used to guide Claude Code
└── README.md
```

---

## Design Decisions & Assumptions

### Data Source

The [yc-oss/open-source-companies](https://github.com/yc-oss/open-source-companies) dataset was chosen as the primary source because:
- It lists real, well-known open-source companies backed by Y Combinator — high signal for analysis.
- It is a single JSON file, making ingestion reliable without scraping.
- Each entry is a GitHub URL, enabling enrichment via the GitHub REST API.

### Seed Fallback

If the remote dataset is unreachable or the GitHub API is rate-limited, `collect.py` falls back to a curated list of 20 well-known companies hard-coded in `SEED_COMPANIES`. This ensures the system works in offline/CI environments without a GitHub token.

### Idempotent Collection

`save_company()` uses `INSERT … ON CONFLICT(name) DO UPDATE SET …` (SQLite upsert). Re-running collection updates stale metadata (star counts, descriptions) without duplicating rows.

### README Enrichment

GitHub project descriptions are often too brief (e.g. "The open source Firebase alternative") for the model to classify confidently. Fetching and stripping the README's opening 600 characters provides richer context at low cost (~1 extra API call per repo).

### LLM Provider Choice

OpenRouter was chosen over calling Gemini directly because:
- It normalises authentication and request format across providers.
- Swapping to a different model (e.g. `anthropic/claude-3-haiku`) requires changing one constant.
- The low cost tier of Gemini 2.5 Flash Lite is sufficient for this dataset size.

### Analysis Caching Strategy

The full raw LLM response is stored in `raw_response` rather than only the parsed fields. This means:
- The cache is the source of truth — re-parsing can recover structured fields without re-calling the API.
- The raw response is auditable for debugging unexpected classifications.

### Strict Module Boundary

All database access goes through `database.py`. No other module imports `sqlite3` or constructs SQL strings. This was enforced via `CLAUDE.md` and makes the storage layer independently testable and replaceable.

---

## Agentic Tool Usage — Claude Code

This project was built end-to-end using **Claude Code** (Anthropic's agentic CLI) running inside VS Code.

### How Claude Code Was Used

**Scaffolding:** The initial file structure, database schema, and module boundaries were generated by giving Claude Code the `CLAUDE.md` spec and asking it to produce a skeleton. Rather than writing boilerplate by hand, the first working version of every file was AI-generated and then reviewed.

**Iterative prompt refinement:** The LLM analysis prompt in `agent.py` went through several iterations:
1. Initial version returned inconsistent industry labels (e.g. "Artificial Intelligence" vs "AI" vs "AI/ML").
2. Claude Code was asked to revise the prompt to enumerate valid industry values — reducing variance.
3. A follow-up iteration added `topics` and `readme_summary` to the context after observing that short descriptions led to generic classifications.

**Debugging:** When Gemini occasionally returned responses wrapped in markdown fences despite being told not to, Claude Code identified the pattern and implemented `_strip_fences()` as a post-processing step.

**Schema migrations:** When `topics` and `readme_summary` columns were added to an already-created database, Claude Code wrote the `ALTER TABLE … ADD COLUMN` migration pattern that is now in `init_db()`.

**MCP server extension:** The two bonus MCP tools — `search_by_topic` and `get_industry_tech_stack` — were added by prompting Claude Code to extend the server and the underlying database queries together.

**CLAUDE.md as a contract:** The `CLAUDE.md` file served as a persistent project specification. Each Claude Code session started by reading it, which meant conventions (no inline SQL, caching rule, API key safety) were consistently enforced across sessions without repeating instructions.

### Evidence of Agentic Workflow

A full session transcript showing how Claude Code was used to build and iterate on this project is included in `TRANSCRIPT.md`.

### Key Takeaways

| Practice | Outcome |
|---|---|
| Writing detailed `CLAUDE.md` upfront | Claude respected module boundaries consistently across sessions |
| Asking Claude to generate then reviewing before running | Caught a potential API key logging bug before it landed |
| Letting Claude own boilerplate (schema, upserts, HTTP client) | Saved hours; human review focused on prompt quality and caching logic |
| Iterating on the LLM prompt via Claude Code | Reached a stable classification taxonomy in 3 rounds |
