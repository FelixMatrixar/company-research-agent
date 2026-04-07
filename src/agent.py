import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import os
import re
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_PROMPT = """\
You are a technology company analyst. Analyze the following GitHub project and classify it.

Project: {name}
Description: {description}
Stars: {stars}
Primary Language: {language}
Topics: {topics}{readme_section}

Return ONLY a JSON object with exactly these keys:
- "industry": the industry sector (e.g. "Developer Tools", "AI/ML", "Security", "Finance", "DevOps")
- "business_model": how it generates value (e.g. "Open Source Library", "Open Source Framework", "SaaS", "CLI Tool")
- "summary": 2-3 sentences describing what this project does
- "use_case": the primary problem it solves, in one sentence

Return only the JSON object. No markdown, no explanation."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def analyze_company(
    company_id: int,
    name: str,
    description: str | None,
    stars: int | None,
    language: str | None,
    topics: str | None = None,
    readme_summary: str | None = None,
) -> dict:
    from database import get_raw_response, save_analysis

    cached = get_raw_response(company_id)
    if cached:
        print(f"  [cache] {name}")
        return json.loads(_strip_fences(cached))

    readme_section = (
        f"\nREADME (excerpt): {readme_summary}" if readme_summary else ""
    )
    prompt = _PROMPT.format(
        name=name,
        description=description or "No description provided",
        stars=stars or 0,
        language=language or "Unknown",
        topics=topics or "none",
        readme_section=readme_section,
    )

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(_strip_fences(raw))

    save_analysis(
        company_id=company_id,
        industry=parsed["industry"],
        business_model=parsed["business_model"],
        summary=parsed["summary"],
        use_case=parsed["use_case"],
        raw_response=raw,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    return parsed


def run() -> None:
    from database import get_unanalyzed_companies

    companies = get_unanalyzed_companies()
    print(f"Analysing {len(companies)} unanalyzed companies...")

    for c in companies:
        print(f"  > {c['name']}")
        try:
            analyze_company(
                company_id=c["id"],
                name=c["name"],
                description=c.get("description"),
                stars=c.get("stars"),
                language=c.get("language"),
                topics=c.get("topics"),
                readme_summary=c.get("readme_summary"),
            )
        except Exception as exc:
            print(f"  [error] {c['name']}: {exc}")


if __name__ == "__main__":
    run()
