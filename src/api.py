import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException

import database

database.init_db()

app = FastAPI(title="Company Research Agent")

_PIPELINE_SECRET = os.environ.get("PIPELINE_SECRET", "")


@app.get("/companies")
def list_companies(
    industry: str | None = None,
    model: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> list[dict]:
    return database.get_all_companies(
        industry=industry,
        business_model=model,
        page=page,
        per_page=per_page,
    )


@app.get("/companies/{company_id}")
def get_company(company_id: int) -> dict:
    company = database.get_company_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.get("/companies/{company_id}/analysis")
def get_company_analysis(company_id: int) -> dict:
    analysis = database.get_analysis_by_company_id(company_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@app.get("/stats")
def get_stats() -> dict:
    return database.get_stats()


@app.post("/pipeline/run")
def run_pipeline(x_api_key: str | None = Header(default=None)) -> dict:
    if not _PIPELINE_SECRET or x_api_key != _PIPELINE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")

    import collect
    import agent

    try:
        collect.run()
        agent.run()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "stats": database.get_stats()}
