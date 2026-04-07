# Agentic Workflow Transcript
**Tool:** Claude Code (VS Code Extension)  
**Project:** Company Research Agent  
**Date:** 2026-04-07

---

## How to Read This

Each exchange shows: my prompt → what Claude Code did → why I prompted that way.  
This documents how I directed, reviewed, and iterated on AI-generated work throughout the build.

---

## Exchange 1 — Plan Before Code

**My prompt:**
```
Read CLAUDE.md first, then confirm the plan back to me — file structure, 
DB schema, and API endpoints. Wait for my approval before creating any files.
```

**What Claude Code did:**  
Read CLAUDE.md, then reflected back the full plan: 6 source files, 2-table schema with foreign key and index, 5 API endpoints, 3 MCP tools, and 5 key constraints it would enforce.

**Why I prompted this way:**  
I wanted to verify Claude Code understood the spec before writing a single line. Asking it to "confirm back" forces it to demonstrate comprehension. The "wait for approval" framing ensures I stay in control of the build sequence.

**What I approved/changed:**  
Plan matched CLAUDE.md exactly. Approved as-is.

---

## Exchange 2 — Scaffold All Files in Dependency Order

**My prompt:**
```
Approved. Build all files now. Start with database.py, then collect.py, 
agent.py, pipeline.py, api.py, mcp_server.py — in that order. Then create 
requirements.txt, .env.example, and .gitignore.
```

**What Claude Code did:**  
Created all 9 files in the specified order. Notable decisions it made autonomously:
- `save_company` uses `ON CONFLICT(name) DO UPDATE` for idempotency
- `get_unanalyzed_companies` uses `LEFT JOIN / WHERE a.id IS NULL` pattern
- `_strip_fences()` in agent.py handles both ` ```json ` and bare ` ``` ` blocks
- `mcp_server.py` used `FastMCP` from the official `mcp` library

**Why I specified the order:**  
`database.py` first ensures every subsequent file can import from it without circular dependency issues. Wrong order causes import errors mid-session.

**What I caught and pushed back on:**  
`collect.py` used BeautifulSoup to scrape `github.com/trending` — fragile, breaks when GitHub changes HTML. I rejected this approach.

---

## Exchange 3 — Switch to GitHub REST API

**My prompt:**
```
Change collect.py to use the GitHub REST API instead of BeautifulSoup scraping. 
Use https://api.github.com/search/repositories with stars:>1000 pushed:>2024-01-01, 
sorted by stars descending. Remove the beautifulsoup4 dependency from requirements.txt.
Add a fallback: if the API is rate-limited or unreachable, load from a hardcoded 
SEED_COMPANIES list of 20 real companies defined at the top of collect.py.
```

**What Claude Code did:**  
Rewrote `collect.py` entirely. Added `SEED_COMPANIES` with 20 real repos as fallback. Handles HTTP 403/429 (rate limit), any `RequestException` (unreachable), and empty result sets — all falling back to seed data. Removed `beautifulsoup4` from `requirements.txt`.

**Why I pushed back on scraping:**  
GitHub's HTML selectors change without notice. A REST API is stable, structured, and rate-limit transparent. The seed fallback matters because the hiring test might be evaluated in an environment with no outbound internet access.

---

## Exchange 4 — Verify Agent Prompt Before Wiring

**My prompt:**
```
Show me agent.py — specifically the system prompt, the OpenRouter call, 
and the fence-stripping logic.
```

**What Claude Code produced:**  
```python
_PROMPT = """
You are a technology company analyst. Analyze the following GitHub project.
Return ONLY a JSON object with exactly these keys:
- "industry", "business_model", "summary", "use_case"
Return only the JSON object. No markdown, no explanation.
"""
```

**What I caught:**  
Two missing items: `HTTP-Referer` header (OpenRouter best practice) and the `topics` field not yet passed to the prompt (added later). Pushed back on the header immediately.

**My follow-up:**
```
Add HTTP-Referer and X-Title headers to the OpenRouter request in agent.py.
```

---

## Exchange 5 — Prompt Engineering: Adding Topics for Richer Context

**My prompt:**
```
Update collect.py to also extract topics from the GitHub API response 
and save it as a comma-separated string in the companies table. Add a topics 
column to the schema in database.py. Pass topics to agent.py alongside name, 
description, stars, and language when calling analyze_company. Update the system 
prompt in agent.py to include topics in the input so Gemini has richer context.
```

**What Claude Code did:**  
Added `topics TEXT` column to schema with `ALTER TABLE` migration. Updated all three SELECT queries. Updated `save_company`, `get_unanalyzed_companies`, `analyze_company` signature, and the prompt template.

**Why this matters:**  
Topics like `["llm", "ai-agents", "rag"]` give the model far more signal than a one-line description. This was the biggest single improvement to analysis quality — the industry classifications became significantly more accurate after this change.

---

## Exchange 6 — Pivot Data Source to YC Open Source Companies

**My prompt:**
```
Replace collect.py entirely. Fetch from:
https://raw.githubusercontent.com/yc-oss/open-source-companies/main/repositories.json
For each entry, extract owner/repo from the url, call GitHub API for description, 
homepage, language, stargazers_count, topics. Filter out entries where description 
is empty. Add 0.5s delay between API calls to avoid rate limiting.
```

**What Claude Code did:**  
Full rewrite of `collect.py`. Added `_extract_slug()`, `_enrich_from_github()`, `_fetch_and_enrich()`. Handles 404s gracefully (skip company). Updated seed fallback to match new schema with `topics` field.

**Why I pivoted:**  
GitHub trending is dominated by community lists, awesome-lists, and personal projects — not companies. The YC open-source dataset is curated real startups with actual products, making the AI analysis more meaningful and the dataset more relevant to the test scenario.

**Result:**  
58 real YC-backed companies collected, 100% analyzed. Industry breakdown: Developer Tools (23), AI/ML (22), DevOps (6), Security (2), others.

---

## Exchange 7 — MCP Server: Three Advanced Tools

**My prompt:**
```
Add three new tools to mcp_server.py and the supporting queries to database.py:

1. search_by_topic(topic: str) — find companies where topics LIKE %topic%
2. Update existing search_companies to also search across summary and use_case columns
3. get_industry_tech_stack(industry: str) — returns language breakdown and avg stars 
   for a given industry using GROUP BY language with COUNT and AVG(stars)
```

**What Claude Code did:**  
Added `get_companies_by_topic()` and `get_industry_aggregation()` to `database.py`. Updated `mcp_server.py` with `search_by_topic` and `get_industry_tech_stack` tools. Extended `search_companies` to scan `summary` and `use_case` fields.

**Verified with:**
```
search_by_topic("ai") → 27 results
get_industry_tech_stack("Developer Tools") → TypeScript dominates (13), avg 12,851 stars
search_companies with query="workflow" hitting summary/use_case → 9 results
```

---

## Exchange 8 — MCP Verification via Claude Desktop

**Setup:**  
Added MCP config from `CLAUDE.md` to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "company-research": {
      "command": "python",
      "args": ["C:\\Users\\celle\\Documents\\company-research-agent\\src\\mcp_server.py"]
    }
  }
}
```

**Queries run through Claude Desktop:**

Query: *"use company research tool to find the most common startup niche"*

Claude Desktop called tools in parallel:
- `search_by_topic("llm")` → 16 results
- `search_by_topic("agent")` → 14 results  
- `search_by_topic("database")` → 6 results
- `search_by_topic("automation")` → 6 results

**Result:** AI Agents / LLM tooling confirmed as the #1 startup niche (~28% of dataset).

Query: *"use company research agent to find the most common tech stack"*

Claude Desktop called:
- `get_industry_tech_stack("Developer Tools")` → TypeScript leads (13 companies)
- `get_industry_tech_stack("AI/ML")` → Python leads (12 companies)
- `get_industry_tech_stack("DevOps")` → Go leads

**This confirms:** The MCP server is fully operational. Agentic tools can query the research database directly using natural language.

---

## Exchange 9 — README Enrichment via GitHub README Fetch

**My prompt:**
```
In collect.py, after fetching repo details, make a second call to fetch the README.
Decode base64 content, strip markdown formatting, take the first 600 characters,
save as readme_summary column. Pass to agent.py as additional context.
```

**What Claude Code did:**  
Added `_strip_markdown()` (strips fenced blocks, inline code, images, links, headings, HTML), `_fetch_readme_summary()` with `README_DELAY = 0.3s`. Updated schema, all queries, agent prompt.

**Verified:**
```python
_strip_markdown("# Hello\n```python\ncode\n```\nThis is **bold**")
# → "Hello This is bold"  ✓
```

README fetch returned `None` during verification due to GitHub rate limit — this is correct behavior, the fallback works as designed.

---

## Prompt Engineering Log

| Version | Change | Problem Solved |
|---|---|---|
| v1 | Basic extraction prompt | Gemini returned markdown fences ~30% of the time |
| v2 | Added "No markdown, no explanation" | Reduced fence rate; added code-level `_strip_fences()` as safety net |
| v3 | Added `Topics: {topics}` field | Industry classifications became significantly more accurate |
| v4 | Switched data source to YC companies | Removed community/list repos; analysis now targets real startups |
| v5 | Added `readme_summary` context | Richer descriptions for repos with sparse GitHub descriptions |

---

## Key Design Decisions Made During Session

**BeautifulSoup → GitHub REST API**  
Scraping is fragile. REST API is structured, versioned, and rate-limit transparent. Seed fallback handles outages.

**GitHub trending → YC open-source dataset**  
Trending repos are dominated by awesome-lists and personal projects. YC dataset is curated real companies — more relevant to the test scenario and produces higher quality AI analysis.

**topics column**  
Single highest-impact change to analysis quality. Topics like `llm, ai-agents, rag` give the model concrete signal that descriptions often lack.

**raw_response cache**  
`get_raw_response()` check before every LLM call. Re-running the pipeline never makes redundant API calls.

**MCP over HTTP**  
Built a proper MCP server alongside the REST API so the data is accessible to agentic tools natively — not just humans via browser.

---

## Final State

```
58 YC-backed companies collected
58/58 analyzed (100% coverage)
5 REST API endpoints live
5 MCP tools operational and verified via Claude Desktop
0 hardcoded credentials
```