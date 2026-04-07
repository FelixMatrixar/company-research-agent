import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import base64
import re
import time
from datetime import datetime, timezone

import requests
import os
from dotenv import load_dotenv


DATASET_URL = (
    "https://raw.githubusercontent.com/yc-oss/open-source-companies"
    "/main/repositories.json"
)
GITHUB_API_URL        = "https://api.github.com/repos/{owner}/{repo}"
GITHUB_README_API_URL = "https://api.github.com/repos/{owner}/{repo}/readme"
HEADERS = {
    "User-Agent": "company-research-agent/1.0",
    "Accept": "application/vnd.github+json",
}
API_DELAY    = 0.5   # seconds between repo API calls
README_DELAY = 0.3   # seconds after README call
README_CHARS = 600   # max characters of stripped README to keep

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)            # fenced code blocks
    text = re.sub(r"`[^`]+`", " ", text)                   # inline code
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)           # images
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links → text
    text = re.sub(r"#{1,6}\s*", "", text)                  # headings
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)        # bold
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)           # italic
    text = re.sub(r"<[^>]+>", " ", text)                   # HTML tags
    text = re.sub(r"[-*+]\s+", "", text)                   # list bullets
    text = re.sub(r"\s+", " ", text)                       # collapse whitespace
    return text.strip()


# Fallback used when the dataset or GitHub API is rate-limited or unreachable.
# readme_summary is None for all seed entries — no README was fetched.
SEED_COMPANIES = [
    {"name": "vercel",       "website": "https://vercel.com",          "description": "Platform for frontend frameworks and static sites",                   "github_url": "https://github.com/vercel/next.js",                 "stars": 128000, "language": "JavaScript", "topics": "react,framework,ssr,frontend",                         "readme_summary": None},
    {"name": "supabase",     "website": "https://supabase.com",        "description": "The open source Firebase alternative",                                "github_url": "https://github.com/supabase/supabase",              "stars": 73000,  "language": "TypeScript", "topics": "database,backend,postgres,firebase-alternative",       "readme_summary": None},
    {"name": "planetscale",  "website": "https://planetscale.com",     "description": "The MySQL-compatible serverless database platform",                   "github_url": "https://github.com/planetscale/vitess",             "stars": 18000,  "language": "Go",         "topics": "database,mysql,serverless,cloud",                      "readme_summary": None},
    {"name": "hashicorp",    "website": "https://terraform.io",        "description": "Infrastructure as Code tool",                                         "github_url": "https://github.com/hashicorp/terraform",            "stars": 43000,  "language": "Go",         "topics": "infrastructure,iac,devops,cloud",                      "readme_summary": None},
    {"name": "grafana",      "website": "https://grafana.com",         "description": "Open source observability and data visualization platform",            "github_url": "https://github.com/grafana/grafana",                "stars": 64000,  "language": "TypeScript", "topics": "observability,monitoring,dashboards,metrics",           "readme_summary": None},
    {"name": "airbyte",      "website": "https://airbyte.com",         "description": "Open-source data integration engine",                                 "github_url": "https://github.com/airbytehq/airbyte",              "stars": 17000,  "language": "Java",       "topics": "data-integration,etl,connectors,pipelines",            "readme_summary": None},
    {"name": "prefect",      "website": "https://prefect.io",          "description": "Workflow orchestration for data and ML pipelines",                    "github_url": "https://github.com/PrefectHQ/prefect",              "stars": 16000,  "language": "Python",     "topics": "workflow,orchestration,data-engineering,mlops",        "readme_summary": None},
    {"name": "dbt-labs",     "website": "https://getdbt.com",          "description": "Transforms data in your warehouse",                                   "github_url": "https://github.com/dbt-labs/dbt-core",              "stars": 10000,  "language": "Python",     "topics": "data,analytics,sql,transformation",                    "readme_summary": None},
    {"name": "retool",       "website": "https://retool.com",          "description": "The fastest way to build internal tools",                             "github_url": "https://github.com/tryretool/retool-utils",         "stars": 2000,   "language": "TypeScript", "topics": "internal-tools,low-code,ui-builder",                   "readme_summary": None},
    {"name": "posthog",      "website": "https://posthog.com",         "description": "Open-source product analytics, session recording, feature flags",     "github_url": "https://github.com/PostHog/posthog",                "stars": 23000,  "language": "Python",     "topics": "analytics,product-analytics,feature-flags,session-replay", "readme_summary": None},
    {"name": "langchain",    "website": "https://langchain.com",       "description": "Build context-aware reasoning applications",                          "github_url": "https://github.com/langchain-ai/langchain",         "stars": 94000,  "language": "Python",     "topics": "llm,ai,agents,rag",                                    "readme_summary": None},
    {"name": "modal",        "website": "https://modal.com",           "description": "Serverless cloud for AI and data applications",                       "github_url": "https://github.com/modal-labs/modal-client",        "stars": 2000,   "language": "Python",     "topics": "serverless,cloud,gpu,ai",                              "readme_summary": None},
    {"name": "huggingface",  "website": "https://huggingface.co",      "description": "The AI community building the future",                                "github_url": "https://github.com/huggingface/transformers",       "stars": 133000, "language": "Python",     "topics": "nlp,ml,transformers,ai",                               "readme_summary": None},
    {"name": "trufflesec",   "website": "https://trufflesecurity.com", "description": "Find, verify, and analyze leaked credentials",                        "github_url": "https://github.com/trufflesecurity/trufflehog",     "stars": 17000,  "language": "Go",         "topics": "security,secrets,credentials,scanning",               "readme_summary": None},
    {"name": "astral",       "website": "https://astral.sh",           "description": "High-performance Python tooling",                                     "github_url": "https://github.com/astral-sh/uv",                   "stars": 38000,  "language": "Rust",       "topics": "python,packaging,tooling,performance",                 "readme_summary": None},
    {"name": "prisma",       "website": "https://prisma.io",           "description": "Next-generation ORM for Node.js and TypeScript",                     "github_url": "https://github.com/prisma/prisma",                  "stars": 40000,  "language": "TypeScript", "topics": "orm,database,typescript,nodejs",                       "readme_summary": None},
    {"name": "n8n",          "website": "https://n8n.io",              "description": "Workflow automation for technical people",                            "github_url": "https://github.com/n8n-io/n8n",                     "stars": 48000,  "language": "TypeScript", "topics": "automation,workflow,no-code,integrations",             "readme_summary": None},
    {"name": "dagger",       "website": "https://dagger.io",           "description": "Application delivery as code that runs anywhere",                     "github_url": "https://github.com/dagger/dagger",                  "stars": 11000,  "language": "Go",         "topics": "ci,cd,devops,containers",                              "readme_summary": None},
    {"name": "weaviate",     "website": "https://weaviate.io",         "description": "Open-source vector database",                                         "github_url": "https://github.com/weaviate/weaviate",              "stars": 11000,  "language": "Go",         "topics": "vector-database,semantic-search,ml,ai",                "readme_summary": None},
    {"name": "mintlify",     "website": "https://mintlify.com",        "description": "Build the documentation you've always wanted",                        "github_url": "https://github.com/mintlify/mint",                  "stars": 4000,   "language": "TypeScript", "topics": "documentation,developer-tools,mdx,api-docs",           "readme_summary": None},
]


def _fetch_dataset() -> dict:
    resp = requests.get(DATASET_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _extract_slug(github_url: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a GitHub URL, or None if unparseable."""
    try:
        path = github_url.rstrip("/").split("github.com/", 1)[1]
        owner, repo = path.split("/", 1)
        return owner, repo.split("/")[0]  # drop any sub-paths
    except (IndexError, ValueError):
        return None


def _fetch_readme_summary(owner: str, repo: str) -> str | None:
    """Fetch, decode, strip, and truncate a repo's README. Returns None on failure."""
    try:
        resp = requests.get(
            GITHUB_README_API_URL.format(owner=owner, repo=repo),
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        content_b64 = resp.json().get("content", "")
        raw = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        stripped = _strip_markdown(raw)
        return stripped[:README_CHARS] if stripped else None
    except requests.exceptions.RequestException:
        return None
    finally:
        time.sleep(README_DELAY)


def _enrich_from_github(owner: str, repo: str) -> dict | None:
    """Call GitHub API for a single repo, then fetch its README. Returns None on hard error."""
    try:
        resp = requests.get(
            GITHUB_API_URL.format(owner=owner, repo=repo),
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        topics = data.get("topics") or []
    except requests.exceptions.RequestException:
        return None

    readme_summary = _fetch_readme_summary(owner, repo)

    return {
        "description":    data.get("description") or None,
        "homepage":       (data.get("homepage") or "").strip() or None,
        "language":       data.get("language") or None,
        "stars":          data.get("stargazers_count"),
        "topics":         ", ".join(topics) if topics else None,
        "readme_summary": readme_summary,
    }


def _fetch_and_enrich(dataset: dict) -> list[dict]:
    repos = []
    total = len(dataset)
    for i, (company_name, entry) in enumerate(dataset.items(), start=1):
        github_url = entry.get("url") if isinstance(entry, dict) else str(entry)
        if not github_url or "github.com" not in github_url:
            continue

        slug = _extract_slug(github_url)
        if not slug:
            continue
        owner, repo = slug

        print(f"  [{i}/{total}] {company_name} ({owner}/{repo})")
        details = _enrich_from_github(owner, repo)

        if details is None:
            print(f"    skipped (API error or 404)")
            time.sleep(API_DELAY)
            continue

        description = details["description"] or f"{company_name} - YC-backed open source company"

        repos.append(
            {
                "name":           company_name,
                "website":        details["homepage"],
                "description":    description,
                "github_url":     github_url,
                "stars":          details["stars"],
                "language":       details["language"],
                "topics":         details["topics"],
                "readme_summary": details["readme_summary"],
            }
        )
        time.sleep(API_DELAY)

    return repos


def _use_seed() -> list[dict]:
    print("  Using SEED_COMPANIES fallback.")
    return SEED_COMPANIES


def run() -> int:
    from database import init_db, save_company

    init_db()
    collected_at = datetime.now(timezone.utc).isoformat()

    print(f"Fetching dataset from {DATASET_URL} ...")
    try:
        dataset = _fetch_dataset()
    except requests.exceptions.RequestException as exc:
        print(f"Failed to fetch dataset: {exc}")
        repos = _use_seed()
    else:
        if not dataset:
            print("Dataset was empty.")
            repos = _use_seed()
        else:
            print(f"Enriching {len(dataset)} entries via GitHub API...")
            repos = _fetch_and_enrich(dataset)
            if not repos:
                print("No repos survived filtering.")
                repos = _use_seed()

    for repo in repos:
        save_company(
            name=repo["name"],
            website=repo.get("website"),
            description=repo.get("description"),
            github_url=repo["github_url"],
            stars=repo.get("stars"),
            language=repo.get("language"),
            topics=repo.get("topics"),
            readme_summary=repo.get("readme_summary"),
            collected_at=collected_at,
        )

    print(f"Collected {len(repos)} companies.")
    return len(repos)


if __name__ == "__main__":
    run()
