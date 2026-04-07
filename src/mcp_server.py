import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

import database

database.init_db()

mcp = FastMCP("company-research")


@mcp.tool()
def search_companies(industry: str | None = None, query: str | None = None) -> list[dict]:
    """Filter companies by industry and/or a keyword matched against name, description, summary, and use_case."""
    results = database.get_all_companies(industry=industry, page=1, per_page=200)
    if query:
        q = query.lower()
        results = [
            c for c in results
            if q in (c.get("name") or "").lower()
            or q in (c.get("description") or "").lower()
            or q in (c.get("summary") or "").lower()
            or q in (c.get("use_case") or "").lower()
        ]
    return results


@mcp.tool()
def get_company(id: int) -> dict:
    """Return a full company record including its analysis."""
    company = database.get_company_by_id(id)
    if not company:
        return {"error": f"No company found with id={id}"}
    return company


@mcp.tool()
def get_stats() -> dict:
    """Return aggregate statistics: total companies, analysis coverage, and industry breakdown."""
    return database.get_stats()

@mcp.tool()
def search_by_topic(topic: str) -> list[dict]:
    """Find companies whose topics contain the given keyword (e.g. 'llm', 'database', 'security')."""
    return database.get_companies_by_topic(topic)


@mcp.tool()
def get_industry_tech_stack(industry: str) -> dict:
    """Return language breakdown and average stars for all companies in a given industry."""
    return database.get_industry_aggregation(industry)

if __name__ == "__main__":
    mcp.run()
