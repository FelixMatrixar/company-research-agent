# Company Research Agent

## Goal
Build an AI-powered company research agent that collects GitHub trending data,
analyses each company with an LLM, stores results in SQLite, and exposes
everything through a FastAPI REST API with an MCP server.

## Stack
- Python 3.11+
- FastAPI + uvicorn
- SQLite (stdlib sqlite3)
- OpenRouter API — model: google/gemini-2.5-flash-lite
- MCP server (mcp library)
- python-dotenv for env vars

## File Structure to Build
```
src/
  collect.py      — fetch GitHub trending repos, map to company schema, save to DB (idempotent)
  agent.py        — call OpenRouter/Gemini, parse JSON response, cache in raw_response column
  database.py     — ALL SQLite queries live here, nowhere else
  api.py          — FastAPI app with all endpoints
  mcp_server.py   — MCP server exposing search_companies, get_company, get_stats tools
  pipeline.py     — orchestrator: runs collect then agent in sequence
data/
  .gitkeep
.env.example
.gitignore
requirements.txt
README.md
TRANSCRIPT.md
```

## Database Schema
```sql
CREATE TABLE companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    website      TEXT,
    description  TEXT,
    github_url   TEXT,
    stars        INTEGER,
    language     TEXT,
    collected_at TEXT NOT NULL
);

CREATE TABLE analysis (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id     INTEGER NOT NULL REFERENCES companies(id),
    industry       TEXT NOT NULL,
    business_model TEXT NOT NULL,
    summary        TEXT NOT NULL,
    use_case       TEXT NOT NULL,
    raw_response   TEXT,
    analyzed_at    TEXT NOT NULL
);

CREATE INDEX idx_analysis_industry ON analysis(industry);
```

## API Endpoints to Build
```
GET  /companies                  — list all, ?industry= ?model= ?page= ?per_page=
GET  /companies/{id}             — single company + embedded analysis
GET  /companies/{id}/analysis    — analysis fields only
GET  /stats                      — totals, coverage %, industry breakdown
POST /pipeline/run               — retrigger pipeline, protected by X-API-Key header
```

## MCP Tools to Build
- search_companies(industry?, query?) — filter by industry or name
- get_company(id) — full record with analysis
- get_stats() — aggregate breakdown

## Critical Rules
- All DB access through database.py only — no inline SQL in api.py or elsewhere
- Check raw_response cache before every LLM call — skip if already analysed
- Load OPENROUTER_API_KEY from environment at module level, raise RuntimeError if missing
- Never log or print the API key
- Gemini often returns markdown fences — always strip them before json.loads()
- collect.py must be idempotent — re-runs must not create duplicate records

## Environment Variables
```
OPENROUTER_API_KEY=sk-or-...
PIPELINE_SECRET=your-random-string
```

## Gitignore Must Cover
- .env
- data/*.db
- __pycache__/
- *.pyc

## MCP Config
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