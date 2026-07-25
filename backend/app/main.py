"""
ReclaimIQ API - Benefit-Underutilization Analytics engine.

FastAPI service exposing member-level benefit valuations, personalized nudges,
and portfolio (issuer) analytics for the dashboard.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.engine import catalog
from app.store import get_store

app = FastAPI(
    title="ReclaimIQ API",
    description="Quantifies unclaimed card-benefit value and generates personalized nudges.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    store = get_store()
    return {"status": "ok", "reference_date": store.engine.ref_date.isoformat(),
            "n_members": len(store.engine.member_ids()), "model": store.model.kind}


@app.get("/api/meta")
def meta():
    store = get_store()
    return {**store.engine.meta, "model_metrics": store.model.metrics}


@app.get("/api/catalog")
def get_catalog():
    return catalog.catalog_as_dict()


@app.get("/api/members")
def members(
    q: str | None = Query(None, description="search by name or id"),
    product: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    rows = get_store().members_list()
    if product:
        rows = [r for r in rows if r["product_id"] == product]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["member_id"].lower()]
    total = len(rows)
    return {"total": total, "items": rows[offset: offset + limit]}


@app.get("/api/members/{member_id}/summary")
def member_summary(member_id: str):
    store = get_store()
    try:
        return store.engine.member_summary(member_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"member {member_id} not found")


@app.get("/api/members/{member_id}/nudges")
def member_nudges(member_id: str, top_k: int = Query(6, le=20)):
    store = get_store()
    try:
        store.engine.member_row(member_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"member {member_id} not found")
    return store.nudges.member_nudges(member_id, top_k=top_k)


@app.get("/api/portfolio")
def portfolio():
    return get_store().portfolio()


@app.get("/api/portfolio/uplift")
def portfolio_uplift():
    return get_store().uplift()
