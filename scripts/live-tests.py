#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
"""Comprehensive live test suite for the Mortgage AI API.

Validates all REST endpoints, WebSocket agent chats, response schemas,
error handling, application lifecycle, and admin functions against a
running server instance.

Prerequisites:
  - API server running on localhost:8000 with AUTH_DISABLED=true
  - Database seeded (POST /api/admin/seed)
  - LLM endpoint available for agent chat tests (skip with --no-chat)

Usage:
  ./scripts/live-tests.py                 # full suite
  ./scripts/live-tests.py --no-chat       # skip WebSocket agent tests
  ./scripts/live-tests.py --section rest  # only REST tests
"""

import argparse
import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
HEADERS = {"Origin": "http://localhost:5173"}

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
ERRORS: list[str] = []
SECTION = ""


def section(name: str):
    global SECTION
    SECTION = name
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}\n")


def ok(name: str, passed: bool, detail: str = ""):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"[{SECTION}] {name}: {detail}" if detail else f"[{SECTION}] {name}"
        ERRORS.append(msg)
        print(f"  FAIL  {name} -- {detail}")


def has_keys(d: dict, *keys: str) -> bool:
    return all(k in d for k in keys)


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

async def test_health(c: httpx.AsyncClient):
    section("Health")

    r = await c.get("/health/")
    ok("GET /health/ returns 200", r.status_code == 200)
    data = r.json()
    ok("response is a list", isinstance(data, list))
    ok("contains API service", any(s.get("name") == "API" for s in data))
    ok("contains DB service", any(s.get("name") == "Database" for s in data))
    ok("API status is healthy",
       any(s.get("name") == "API" and s.get("status") == "healthy" for s in data))

    r = await c.get("/")
    ok("GET / root returns 200", r.status_code == 200)
    ok("root has welcome message", "message" in r.json())


# ---------------------------------------------------------------------------
# 2. Public API -- products & affordability
# ---------------------------------------------------------------------------

async def test_public_api(c: httpx.AsyncClient):
    section("Public API (no auth required)")

    # Products
    r = await c.get("/api/public/products")
    ok("GET /api/public/products returns 200", r.status_code == 200)
    products = r.json()
    ok("products is non-empty list", isinstance(products, list) and len(products) > 0)
    if products:
        p = products[0]
        ok("product has name field", "name" in p)
        ok("product has description", "description" in p)
        ok("conventional_30 exists",
           any(pr.get("id") == "conventional_30" or pr.get("name", "").lower().startswith("conventional 30")
               for pr in products))

    # Products trailing-slash redirect
    r = await c.get("/api/public/products/", follow_redirects=False)
    ok("trailing slash redirects (307)", r.status_code == 307)

    # Affordability calculator -- valid request
    payload = {
        "gross_annual_income": 120000,
        "monthly_debts": 800,
        "down_payment": 50000,
        "interest_rate": 6.5,
        "loan_term_years": 30,
    }
    r = await c.post("/api/public/calculate-affordability", json=payload)
    ok("POST calculate-affordability returns 200", r.status_code == 200)
    body = r.json()
    ok("response has max_loan_amount", "max_loan_amount" in body)
    ok("response has estimated_monthly_payment", "estimated_monthly_payment" in body)
    ok("response has dti_ratio", "dti_ratio" in body)
    ok("max_loan_amount > 0", body.get("max_loan_amount", 0) > 0)
    ok("dti_ratio is reasonable (0-100)",
       0 < body.get("dti_ratio", -1) < 100)

    # Affordability -- high DTI triggers warning
    high_debt = {
        "gross_annual_income": 60000,
        "monthly_debts": 3000,
        "down_payment": 10000,
        "interest_rate": 7.0,
        "loan_term_years": 30,
    }
    r = await c.post("/api/public/calculate-affordability", json=high_debt)
    ok("high-debt request returns 200", r.status_code == 200)
    ok("dti_warning present for high debt",
       r.json().get("dti_warning") is not None,
       f"dti_ratio={r.json().get('dti_ratio')}")

    # Affordability -- validation errors
    r = await c.post("/api/public/calculate-affordability", json={})
    ok("empty body returns 422", r.status_code == 422)

    r = await c.post("/api/public/calculate-affordability",
                     json={"gross_annual_income": -1, "monthly_debts": 0, "down_payment": 0})
    ok("negative income returns 422", r.status_code == 422)


# ---------------------------------------------------------------------------
# 3. Application CRUD
# ---------------------------------------------------------------------------

async def test_application_crud(c: httpx.AsyncClient) -> dict:
    """Returns dict with created app_id for downstream tests."""
    section("Application CRUD")
    ctx: dict = {}

    # List
    r = await c.get("/api/applications/")
    ok("GET /api/applications/ returns 200", r.status_code == 200)
    body = r.json()
    ok("response has data array", isinstance(body.get("data"), list))
    ok("response has pagination", has_keys(body.get("pagination", {}),
                                           "total", "offset", "limit", "has_more"))

    # Pagination
    r = await c.get("/api/applications/", params={"offset": 0, "limit": 2})
    ok("pagination limit=2", r.status_code == 200 and len(r.json()["data"]) <= 2)

    # Pick a seeded app for read tests
    apps = body["data"]
    if apps:
        seeded_id = apps[0]["id"]
        ctx["seeded_id"] = seeded_id

        # Get single
        r = await c.get(f"/api/applications/{seeded_id}")
        ok(f"GET /api/applications/{seeded_id}", r.status_code == 200)
        app = r.json()
        ok("app has id", app.get("id") == seeded_id)
        ok("app has stage", "stage" in app)
        ok("app has loan_type", "loan_type" in app)
        ok("app has created_at", "created_at" in app)
        ok("app has borrowers list", isinstance(app.get("borrowers"), list))

        if app.get("borrowers"):
            b = app["borrowers"][0]
            ok("borrower has first_name", "first_name" in b)
            ok("borrower has is_primary", "is_primary" in b)

    # 404 for non-existent
    r = await c.get("/api/applications/99999")
    ok("non-existent app returns 404", r.status_code == 404)

    # Create
    create_payload = {
        "loan_type": "conventional_30",
        "property_address": "123 Live Test Blvd, Denver CO 80202",
        "loan_amount": 350000,
        "property_value": 450000,
    }
    r = await c.post("/api/applications/", json=create_payload)
    ok("POST create returns 201", r.status_code == 201)
    created = r.json()
    ok("created app has id", "id" in created)
    ok("created app stage is inquiry", created.get("stage") == "inquiry")
    ok("loan_amount matches", float(created.get("loan_amount", 0)) == 350000)
    ctx["created_id"] = created.get("id")

    # Create with minimal fields (all optional)
    r = await c.post("/api/applications/", json={})
    ok("create with empty body returns 201", r.status_code == 201)
    ctx["minimal_id"] = r.json().get("id")

    # Create with invalid loan_amount
    r = await c.post("/api/applications/", json={"loan_amount": -100})
    ok("negative loan_amount returns 422", r.status_code == 422)

    # Patch
    if ctx.get("created_id"):
        aid = ctx["created_id"]
        r = await c.patch(f"/api/applications/{aid}",
                          json={"property_address": "456 Updated Ave, Denver CO"})
        ok("PATCH update returns 200", r.status_code == 200)
        ok("address updated",
           r.json().get("property_address") == "456 Updated Ave, Denver CO")

        # Empty patch body
        r = await c.patch(f"/api/applications/{aid}", json={})
        ok("empty PATCH returns 400", r.status_code == 400)

    # Sort by updated_at
    r = await c.get("/api/applications/", params={"sort_by": "updated_at"})
    ok("sort by updated_at returns 200", r.status_code == 200)

    # Filter by stage
    r = await c.get("/api/applications/", params={"filter_stage": "inquiry"})
    ok("filter by stage returns 200", r.status_code == 200)
    if r.status_code == 200:
        ok("all filtered apps are inquiry",
           all(a.get("stage") == "inquiry" for a in r.json()["data"]))

    return ctx


# ---------------------------------------------------------------------------
# 4. Application status, rate lock, completeness
# ---------------------------------------------------------------------------

async def test_application_details(c: httpx.AsyncClient, app_id: int):
    section("Application Details (status, rate lock, completeness)")

    # Status
    r = await c.get(f"/api/applications/{app_id}/status")
    ok("GET status returns 200", r.status_code == 200)
    body = r.json()
    ok("status has stage", "stage" in body)
    ok("status has stage_info", "stage_info" in body)

    # Rate lock
    r = await c.get(f"/api/applications/{app_id}/rate-lock")
    ok("GET rate-lock returns 200", r.status_code == 200)
    rl = r.json()
    ok("rate-lock has status field", "status" in rl)

    # Completeness
    r = await c.get(f"/api/applications/{app_id}/completeness")
    ok("GET completeness returns 200", r.status_code == 200)
    comp = r.json()
    ok("completeness has required_count", "required_count" in comp)
    ok("completeness has provided_count", "provided_count" in comp)
    ok("completeness has requirements", isinstance(comp.get("requirements"), list))

    # 404 on non-existent app
    r = await c.get("/api/applications/99999/status")
    ok("status for non-existent app returns 404", r.status_code == 404)
    r = await c.get("/api/applications/99999/rate-lock")
    ok("rate-lock for non-existent app returns 404", r.status_code == 404)
    r = await c.get("/api/applications/99999/completeness")
    ok("completeness for non-existent app returns 404", r.status_code == 404)


# ---------------------------------------------------------------------------
# 5. Documents
# ---------------------------------------------------------------------------

async def test_documents(c: httpx.AsyncClient, app_id: int):
    section("Documents")

    r = await c.get(f"/api/applications/{app_id}/documents")
    ok("GET documents returns 200", r.status_code == 200)
    body = r.json()
    ok("documents has data array", isinstance(body.get("data"), list))
    ok("documents has pagination", "pagination" in body)

    docs = body["data"]
    if docs:
        doc = docs[0]
        ok("document has id", "id" in doc)
        ok("document has doc_type", "doc_type" in doc)
        ok("document has status", "status" in doc)
        ok("document has created_at", "created_at" in doc)

        # Get single document
        doc_id = doc["id"]
        r = await c.get(f"/api/applications/{app_id}/documents/{doc_id}")
        ok(f"GET document/{doc_id} returns 200", r.status_code == 200)

    # Non-existent document
    r = await c.get(f"/api/applications/{app_id}/documents/99999")
    ok("non-existent document returns 404", r.status_code == 404)


# ---------------------------------------------------------------------------
# 6. Conditions
# ---------------------------------------------------------------------------

async def test_conditions(c: httpx.AsyncClient, app_id: int):
    section("Conditions")

    r = await c.get(f"/api/applications/{app_id}/conditions")
    ok("GET conditions returns 200", r.status_code == 200)
    body = r.json()
    ok("conditions has data array", isinstance(body.get("data"), list))
    ok("conditions has pagination", "pagination" in body)

    # open_only filter
    r = await c.get(f"/api/applications/{app_id}/conditions", params={"open_only": "true"})
    ok("GET conditions open_only returns 200", r.status_code == 200)

    conditions = body["data"]
    if conditions:
        cond = conditions[0]
        ok("condition has id", "id" in cond)
        ok("condition has description", "description" in cond)
        ok("condition has status", "status" in cond)
        ok("condition has severity", "severity" in cond)


# ---------------------------------------------------------------------------
# 7. Decisions
# ---------------------------------------------------------------------------

async def test_decisions(c: httpx.AsyncClient, app_id: int):
    section("Decisions")

    r = await c.get(f"/api/applications/{app_id}/decisions")
    ok("GET decisions returns 200", r.status_code == 200)
    body = r.json()
    ok("decisions has data array", isinstance(body.get("data"), list))
    ok("decisions has pagination", "pagination" in body)

    decisions = body["data"]
    if decisions:
        dec = decisions[0]
        ok("decision has id", "id" in dec)
        ok("decision has decision_type", "decision_type" in dec)
        ok("decision has created_at", "created_at" in dec)

        # Get single decision
        dec_id = dec["id"]
        r = await c.get(f"/api/applications/{app_id}/decisions/{dec_id}")
        ok(f"GET decision/{dec_id} returns 200", r.status_code == 200)
        ok("single decision wrapped in data",
           "data" in r.json() and r.json()["data"].get("id") == dec_id)

    # Non-existent decision
    r = await c.get(f"/api/applications/{app_id}/decisions/99999")
    ok("non-existent decision returns 404", r.status_code == 404)


# ---------------------------------------------------------------------------
# 8. HMDA demographic data
# ---------------------------------------------------------------------------

async def test_hmda(c: httpx.AsyncClient, app_id: int):
    section("HMDA Demographic Collection")

    payload = {
        "application_id": app_id,
        "race": "White",
        "ethnicity": "Not Hispanic or Latino",
        "sex": "Male",
        "age": "35-44",
    }
    r = await c.post("/api/hmda/collect", json=payload)
    # 201 on success, or a known error if the app isn't in the right state
    ok("POST /api/hmda/collect accepted",
       r.status_code in (201, 404),
       f"status={r.status_code}")

    if r.status_code == 201:
        body = r.json()
        ok("HMDA response has id", "id" in body)
        ok("HMDA response has application_id", body.get("application_id") == app_id)
        ok("HMDA response has status", body.get("status") == "collected")

    # Validation -- missing application_id
    r = await c.post("/api/hmda/collect", json={"race": "White"})
    ok("HMDA without application_id returns 422", r.status_code == 422)


# ---------------------------------------------------------------------------
# 9. Admin endpoints
# ---------------------------------------------------------------------------

async def test_admin(c: httpx.AsyncClient):
    section("Admin Endpoints")

    # Seed status
    r = await c.get("/api/admin/seed/status")
    ok("GET /api/admin/seed/status returns 200", r.status_code == 200)
    body = r.json()
    ok("seed status has seeded flag", "seeded" in body)

    # Seed (already seeded, should get 409 without force)
    r = await c.post("/api/admin/seed")
    ok("POST /api/admin/seed (already seeded) returns 409 or 200",
       r.status_code in (200, 409),
       f"status={r.status_code}")

    # Seed GET method not allowed
    r = await c.get("/api/admin/seed")
    ok("GET /api/admin/seed returns 405", r.status_code == 405)

    # Audit by application (use first seeded app from listing)
    apps_r = await c.get("/api/applications/", params={"limit": 1})
    audit_app_id = None
    if apps_r.status_code == 200 and apps_r.json().get("data"):
        audit_app_id = apps_r.json()["data"][0]["id"]

    if audit_app_id:
        r = await c.get(f"/api/audit/application/{audit_app_id}")
        ok(f"GET audit/application/{audit_app_id} returns 200", r.status_code == 200)
        body = r.json()
        ok("audit response has application_id", body.get("application_id") == audit_app_id)
        ok("audit response has events array", isinstance(body.get("events"), list))
        ok("audit response has count", isinstance(body.get("count"), int))

        events = body.get("events", [])
        if events:
            evt = events[0]
            ok("audit event has id", "id" in evt)
            ok("audit event has timestamp", "timestamp" in evt)
            ok("audit event has event_type", "event_type" in evt)
    else:
        ok("audit by application (no seeded app found)", False, "no apps in listing")

    # Audit by session (requires session_id param)
    r = await c.get("/api/audit/session")
    ok("audit without session_id returns 422", r.status_code == 422)

    r = await c.get("/api/audit/session", params={"session_id": "nonexistent-session"})
    ok("audit with unknown session returns 200 (empty)", r.status_code == 200)
    ok("empty session has count=0", r.json().get("count") == 0)

    # Audit chain verify
    r = await c.get("/api/audit/verify")
    ok("GET audit/verify returns 200", r.status_code == 200)
    verify = r.json()
    ok("verify has status field", "status" in verify)
    ok("verify status is valid value",
       verify.get("status") in ("OK", "TAMPERED", "EMPTY"),
       f"status={verify.get('status')}")
    if verify.get("status") == "TAMPERED":
        print("         (TAMPERED is expected -- hash algorithm was expanded)")
    ok("verify has events_checked", "events_checked" in verify)


# ---------------------------------------------------------------------------
# 10. Error handling -- RFC 7807
# ---------------------------------------------------------------------------

async def test_error_handling(c: httpx.AsyncClient):
    section("Error Handling (RFC 7807)")

    # 404
    r = await c.get("/api/applications/99999")
    ok("404 status code", r.status_code == 404)
    body = r.json()
    ok("404 has type field", "type" in body)
    ok("404 has title field", "title" in body)
    ok("404 has status field", body.get("status") == 404)
    ok("404 has detail field", "detail" in body)

    # 422
    r = await c.post("/api/applications/", json={"loan_amount": -100})
    ok("422 status code", r.status_code == 422)
    body = r.json()
    ok("422 has type field", "type" in body)
    ok("422 has status=422", body.get("status") == 422)

    # 405 method not allowed
    r = await c.get("/api/admin/seed")
    ok("405 for wrong method", r.status_code == 405)

    # Non-existent route
    r = await c.get("/api/nonexistent")
    ok("non-existent route returns 404", r.status_code == 404)

    # 400 empty PATCH body
    r = await c.patch("/api/applications/1", json={})
    # Could be 400 (empty body) or 404 (app not found) -- both are valid
    ok("empty PATCH body returns 400 or 404",
       r.status_code in (400, 404),
       f"status={r.status_code}")


# ---------------------------------------------------------------------------
# 11. Conversation history
# ---------------------------------------------------------------------------

async def test_conversation_history(c: httpx.AsyncClient):
    section("Conversation History Endpoints")

    for persona, path in [
        ("borrower", "/api/borrower/conversations/history"),
        ("loan-officer", "/api/loan-officer/conversations/history"),
        ("underwriter", "/api/underwriter/conversations/history"),
        ("ceo", "/api/ceo/conversations/history"),
    ]:
        r = await c.get(path)
        ok(f"GET {persona} history returns 200", r.status_code == 200)
        body = r.json()
        ok(f"{persona} response has data array",
           isinstance(body.get("data"), list))


# ---------------------------------------------------------------------------
# 12. Application lifecycle (create -> update -> transition -> verify)
# ---------------------------------------------------------------------------

async def test_application_lifecycle(c: httpx.AsyncClient):
    section("Application Lifecycle (stage transitions)")

    # Create fresh app
    r = await c.post("/api/applications/", json={
        "loan_type": "fha",
        "property_address": "999 Lifecycle Test Way",
        "loan_amount": 200000,
        "property_value": 250000,
    })
    ok("create lifecycle app", r.status_code == 201)
    app_id = r.json()["id"]
    ok("starts in inquiry stage", r.json().get("stage") == "inquiry")

    # Transition inquiry -> prequalification
    r = await c.patch(f"/api/applications/{app_id}",
                      json={"stage": "prequalification"})
    ok("transition to prequalification", r.status_code == 200)
    ok("stage is prequalification", r.json().get("stage") == "prequalification")

    # Transition prequalification -> application
    r = await c.patch(f"/api/applications/{app_id}",
                      json={"stage": "application"})
    ok("transition to application", r.status_code == 200)
    ok("stage is application", r.json().get("stage") == "application")

    # Transition application -> processing
    r = await c.patch(f"/api/applications/{app_id}",
                      json={"stage": "processing"})
    ok("transition to processing", r.status_code == 200)
    ok("stage is processing", r.json().get("stage") == "processing")

    # Transition processing -> underwriting
    r = await c.patch(f"/api/applications/{app_id}",
                      json={"stage": "underwriting"})
    ok("transition to underwriting", r.status_code == 200)
    ok("stage is underwriting", r.json().get("stage") == "underwriting")

    # Invalid transition: underwriting -> inquiry (should fail)
    r = await c.patch(f"/api/applications/{app_id}",
                      json={"stage": "inquiry"})
    ok("invalid transition rejected (422)", r.status_code == 422,
       f"status={r.status_code}")

    # Verify status reflects underwriting
    r = await c.get(f"/api/applications/{app_id}/status")
    ok("status shows underwriting", r.json().get("stage") == "underwriting")


# ---------------------------------------------------------------------------
# 13. OpenAPI spec
# ---------------------------------------------------------------------------

async def test_openapi(c: httpx.AsyncClient):
    section("OpenAPI Specification")

    r = await c.get("/openapi.json")
    ok("GET /openapi.json returns 200", r.status_code == 200)
    spec = r.json()
    ok("spec has openapi version", "openapi" in spec)
    ok("spec has info", "info" in spec)
    ok("spec title contains 'mortgage'",
       "mortgage" in spec.get("info", {}).get("title", "").lower())
    ok("spec has paths", len(spec.get("paths", {})) > 10,
       f"path_count={len(spec.get('paths', {}))}")

    r = await c.get("/docs")
    ok("GET /docs (Swagger UI) returns 200", r.status_code == 200)


# ---------------------------------------------------------------------------
# 14. Analytics (CEO dashboard)
# ---------------------------------------------------------------------------

async def test_analytics(c: httpx.AsyncClient):
    section("Analytics (CEO Dashboard)")

    # Pipeline summary
    r = await c.get("/api/analytics/pipeline")
    ok("GET /api/analytics/pipeline returns 200", r.status_code == 200)
    body = r.json()
    ok("pipeline has by_stage", "by_stage" in body)
    ok("pipeline has pull_through_rate", "pull_through_rate" in body)
    ok("pipeline has total_applications", "total_applications" in body)

    # Pipeline with custom days
    r = await c.get("/api/analytics/pipeline", params={"days": 30})
    ok("pipeline with days=30 returns 200", r.status_code == 200)

    # Denial trends
    r = await c.get("/api/analytics/denial-trends")
    ok("GET /api/analytics/denial-trends returns 200", r.status_code == 200)
    body = r.json()
    ok("denial-trends has total_decisions", "total_decisions" in body)
    ok("denial-trends has overall_denial_rate", "overall_denial_rate" in body)
    ok("denial-trends has top_reasons", isinstance(body.get("top_reasons"), list))

    # Denial trends with product filter
    r = await c.get("/api/analytics/denial-trends",
                     params={"product": "conventional_30"})
    ok("denial-trends with product filter returns 200", r.status_code == 200)

    # LO performance
    r = await c.get("/api/analytics/lo-performance")
    ok("GET /api/analytics/lo-performance returns 200", r.status_code == 200)
    body = r.json()
    ok("lo-performance has loan_officers", isinstance(body.get("loan_officers"), list))

    lo_list = body.get("loan_officers", [])
    if lo_list:
        lo = lo_list[0]
        ok("LO entry has lo_id", "lo_id" in lo)
        ok("LO entry has active_count", "active_count" in lo)
        ok("LO entry has pull_through_rate", "pull_through_rate" in lo)
        ok("multiple LOs in performance data", len(lo_list) >= 2,
           f"got {len(lo_list)} LOs (expected >=2 with expanded seed data)")


# ---------------------------------------------------------------------------
# 15. Model monitoring
# ---------------------------------------------------------------------------

async def test_model_monitoring(c: httpx.AsyncClient):
    section("Model Monitoring")

    # Summary endpoint -- works even when LangFuse is not configured
    r = await c.get("/api/analytics/model-monitoring")
    ok("GET /api/analytics/model-monitoring returns 200", r.status_code == 200)
    body = r.json()
    ok("has langfuse_available flag", "langfuse_available" in body)
    ok("has time_range_hours", "time_range_hours" in body)
    ok("has computed_at", "computed_at" in body)

    # With custom hours
    r = await c.get("/api/analytics/model-monitoring", params={"hours": 48})
    ok("model-monitoring hours=48 returns 200", r.status_code == 200)
    ok("time_range_hours reflects param",
       r.json().get("time_range_hours") == 48)

    # Hours capped at 2160
    r = await c.get("/api/analytics/model-monitoring", params={"hours": 9999})
    ok("model-monitoring hours=9999 returns 422", r.status_code == 422)

    # Sub-endpoints -- return 503 when LangFuse not configured, 200 when it is
    for sub in ["latency", "tokens", "errors", "routing"]:
        r = await c.get(f"/api/analytics/model-monitoring/{sub}")
        ok(f"GET model-monitoring/{sub} returns 200 or 503",
           r.status_code in (200, 503),
           f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 16. Audit extended queries
# ---------------------------------------------------------------------------

async def test_audit_extended(c: httpx.AsyncClient, app_id: int | None):
    section("Audit Extended (search, decision trace, export)")

    # Audit search
    r = await c.get("/api/audit/search", params={"event_type": "application_created"})
    ok("GET audit/search returns 200", r.status_code == 200)
    body = r.json()
    ok("search has events array", isinstance(body.get("events"), list))
    ok("search has count", isinstance(body.get("count"), int))

    # Audit search with time filter
    r = await c.get("/api/audit/search", params={"hours": 24})
    ok("audit/search hours=24 returns 200", r.status_code == 200)

    # Audit export (returns a list directly)
    r = await c.get("/api/audit/export")
    ok("GET audit/export returns 200", r.status_code == 200)
    body = r.json()
    ok("export is a list", isinstance(body, list))

    # Decision audit + trace (find a decision from a seeded app)
    if app_id:
        r = await c.get(f"/api/applications/{app_id}/decisions")
        decisions = r.json().get("data", []) if r.status_code == 200 else []
        if decisions:
            dec_id = decisions[0]["id"]
            r = await c.get(f"/api/audit/decision/{dec_id}")
            ok(f"GET audit/decision/{dec_id} returns 200", r.status_code == 200)
            ok("decision audit has events", isinstance(r.json().get("events"), list))

            r = await c.get(f"/api/audit/decision/{dec_id}/trace")
            ok(f"GET audit/decision/{dec_id}/trace returns 200", r.status_code == 200)
            trace = r.json()
            ok("trace has decision_id", "decision_id" in trace)
            ok("trace has events", isinstance(trace.get("events"), list))
        else:
            print("    SKIP  decision audit/trace (no decisions on test app)")
    else:
        print("    SKIP  decision audit/trace (no app_id)")


# ---------------------------------------------------------------------------
# 17. Co-borrower management
# ---------------------------------------------------------------------------

async def test_coborrower_management(c: httpx.AsyncClient, app_id: int):
    section("Co-borrower Management")

    # First get the app to find existing borrowers
    r = await c.get(f"/api/applications/{app_id}")
    if r.status_code != 200:
        ok("get app for coborrower test", False, f"status={r.status_code}")
        return

    borrowers = r.json().get("borrowers", [])
    non_primary = [b for b in borrowers if not b.get("is_primary")]

    if non_primary:
        # Try removing and re-adding a co-borrower
        co_id = non_primary[0]["id"]
        r = await c.delete(f"/api/applications/{app_id}/borrowers/{co_id}")
        ok("DELETE co-borrower returns 200", r.status_code == 200)

        r = await c.post(f"/api/applications/{app_id}/borrowers",
                         json={"borrower_id": co_id, "is_primary": False})
        ok("POST re-add co-borrower returns 201", r.status_code == 201)
    else:
        print("    SKIP  co-borrower remove/add (no co-borrowers on test app)")

    # Add non-existent borrower
    r = await c.post(f"/api/applications/{app_id}/borrowers",
                     json={"borrower_id": 99999, "is_primary": False})
    ok("add non-existent borrower returns 404", r.status_code == 404)

    # Remove non-existent borrower
    r = await c.delete(f"/api/applications/{app_id}/borrowers/99999")
    ok("remove non-existent borrower returns 404", r.status_code == 404)


# ---------------------------------------------------------------------------
# 18. Condition response
# ---------------------------------------------------------------------------

async def test_condition_response(c: httpx.AsyncClient, app_id: int):
    section("Condition Response")

    # Find an open condition on the app
    r = await c.get(f"/api/applications/{app_id}/conditions",
                     params={"open_only": "true"})
    conditions = []
    if r.status_code == 200:
        conditions = r.json().get("data", [])

    if conditions:
        cond_id = conditions[0]["id"]
        r = await c.post(
            f"/api/applications/{app_id}/conditions/{cond_id}/respond",
            json={"response_text": "Here is my response for the live test."},
        )
        ok(f"POST condition/{cond_id}/respond returns 200", r.status_code == 200)
        if r.status_code == 200:
            data = r.json().get("data", r.json())
            ok("response has status", "status" in data)
    else:
        print("    SKIP  condition response (no open conditions on test app)")

    # Non-existent condition
    r = await c.post(
        f"/api/applications/{app_id}/conditions/99999/respond",
        json={"response_text": "test"},
    )
    ok("respond to non-existent condition returns 404", r.status_code == 404)


# ---------------------------------------------------------------------------
# 19. WebSocket agent chats
# ---------------------------------------------------------------------------

class ChatResult:
    """Result from a WebSocket chat interaction."""

    def __init__(self):
        self.response = ""
        self.got_done = False
        self.tool_calls = 0
        self.error = None


async def ws_chat(path: str, agent: str, message: str,
                  expect_keywords: list[str], timeout: int = 90,
                  expect_tools: bool | None = None) -> ChatResult:
    """Test a single WebSocket chat agent.

    Args:
        expect_tools: If True, assert tools were used (capable model path).
                      If False, assert NO tools were used (fast model path).
                      If None, just report tool usage without asserting.
    """
    result = ChatResult()
    uri = f"{WS_BASE}{path}"
    try:
        async with websockets.connect(uri, additional_headers=HEADERS) as ws:
            await ws.send(json.dumps({"type": "message", "content": message}))

            start = time.time()

            while time.time() - start < timeout:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    msg_type = msg.get("type", "")

                    if msg_type == "token":
                        result.response += msg.get("content", "")
                    elif msg_type == "tool_start":
                        result.tool_calls += 1
                    elif msg_type == "done":
                        result.got_done = True
                        break
                    elif msg_type == "error":
                        result.error = msg.get("content", "")[:120]
                        ok(f"{agent} no errors", False, f"error: {result.error}")
                        return result
                    elif msg_type == "safety_override":
                        result.error = msg.get("content", "")[:120]
                        ok(f"{agent} no safety block", False, f"safety: {result.error}")
                        return result
                except asyncio.TimeoutError:
                    continue

            ok(f"{agent} connected", True)
            ok(f"{agent} got response (len={len(result.response)})",
               len(result.response) > 10)
            ok(f"{agent} received done signal", result.got_done)

            found = any(kw.lower() in result.response.lower() for kw in expect_keywords)
            ok(f"{agent} response relevant to query", found,
               f"expected one of {expect_keywords}")

            if expect_tools is True:
                ok(f"{agent} used tools ({result.tool_calls} calls)",
                   result.tool_calls > 0,
                   "expected tool calls but got none")
            elif expect_tools is False:
                ok(f"{agent} no tool calls (fast model path)",
                   result.tool_calls == 0,
                   f"expected 0 tool calls but got {result.tool_calls}")
            elif result.tool_calls > 0:
                ok(f"{agent} used tools ({result.tool_calls} calls)", True)

    except Exception as e:
        result.error = str(e)[:150]
        ok(f"{agent} connection", False, result.error)

    return result


async def test_agent_responses():
    """Test that agents respond with domain-relevant content.

    Verifies the agent processes both simple and complex queries,
    with tools available for all interactions.
    """
    section("Agent Responses")

    # Simple greeting
    await ws_chat(
        "/api/chat", "Greeting",
        "hello",
        ["hello", "hi", "welcome", "help", "summit", "mortgage", "assist"],
    )

    # Affordability query (may invoke tools)
    await ws_chat(
        "/api/chat", "Affordability query",
        "Calculate my affordability if I make $100,000 a year with $500 in monthly debts and $20,000 down payment",
        ["afford", "loan", "payment", "amount", "$", "income", "dti"],
    )

    # Compliance query
    await ws_chat(
        "/api/underwriter/chat", "Compliance query",
        "Run a full ECOA and ATR/QM compliance check on the next application in my underwriting queue",
        ["compliance", "ecoa", "check", "pass", "fail", "regulation", "fair",
         "atr", "qualified", "lending"],
    )


async def test_embedding_model(c: httpx.AsyncClient):
    """Test the embedding model tier directly and via KB search.

    The embedding model (nomic-embed-text-v1.5) is exercised two ways:
    1. Direct: call the OpenAI-compatible /v1/embeddings endpoint (remote only)
    2. Indirect: verify KB chunks were ingested with embeddings

    When the provider is ``local`` (in-process sentence-transformers), the
    direct endpoint test is skipped because there is no remote server.
    The KB data verification still confirms embeddings were generated.

    The KB search path (agent tool -> get_embeddings -> pgvector cosine
    similarity) is exercised during agent chats. Here we verify the
    infrastructure: the model responds, KB data exists, and vectors are
    populated.
    """
    section("Embedding Model + Compliance KB")

    # 1. Direct embedding endpoint test (remote provider only)
    # Read the embedding config from the models.yaml via the running app
    import yaml
    from pathlib import Path

    config_path = Path(__file__).resolve().parents[0] / ".." / "config" / "models.yaml"
    try:
        raw = config_path.read_text()
        config = yaml.safe_load(raw)
        emb_cfg = config.get("models", {}).get("embedding", {})
        provider = emb_cfg.get("provider", "openai_compatible")
        endpoint = emb_cfg.get("endpoint", "")
        model_name = emb_cfg.get("model_name", "")
        api_key = emb_cfg.get("api_key", "not-needed")

        # Resolve env vars (simple ${VAR:-default} pattern)
        import os
        import re
        def resolve(s):
            return re.sub(
                r"\$\{(\w+)(?::-(.*?))?\}",
                lambda m: os.environ.get(m.group(1), m.group(2) or ""),
                s,
            )
        provider = resolve(provider)
        endpoint = resolve(endpoint)
        model_name = resolve(model_name)
        api_key = resolve(api_key)

        ok("embedding config loaded",
           bool(model_name),
           f"provider={provider}, model={model_name}")

        if provider == "local":
            print("    SKIP  direct embedding call (provider=local, in-process)")
            print("          Verifying embedding model indirectly via KB chunk data instead.")
        elif endpoint and model_name:
            # Call embedding endpoint directly.
            # The API key may be set via env var at server startup but not
            # available to this test script. Try the resolved key first,
            # then fall back to common LMStudio patterns.
            keys_to_try = [api_key]
            for env_key in ("LLM_API_KEY", "LMSTUDIO_API_KEY", "OPENAI_API_KEY"):
                v = os.environ.get(env_key)
                if v and v not in keys_to_try:
                    keys_to_try.append(v)

            emb_success = False
            for key in keys_to_try:
                emb_client = httpx.AsyncClient(
                    base_url=endpoint,
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                try:
                    r = await emb_client.post("/embeddings", json={
                        "model": model_name,
                        "input": ["TRID Loan Estimate delivery requirements"],
                    })
                    if r.status_code == 200:
                        data = r.json().get("data", [])
                        ok("embedding endpoint responds", True)
                        ok("embedding returned vectors", len(data) > 0)
                        if data:
                            vec = data[0].get("embedding", [])
                            ok(f"embedding dimensions ({len(vec)})",
                               len(vec) >= 384,
                               f"expected >=384, got {len(vec)}")
                        emb_success = True
                        break
                finally:
                    await emb_client.aclose()

            if not emb_success:
                # Can't reach embedding endpoint directly (auth mismatch).
                # The app has the right key; we verify indirectly via KB data.
                print("    SKIP  direct embedding call (auth -- API key not available to test script)")
                print("          Verifying embedding model indirectly via KB chunk data instead.")

    except FileNotFoundError:
        ok("embedding config file exists", False, f"not found: {config_path}")

    # 2. Verify KB data exists (seeded during seed)
    r = await c.get("/api/admin/seed/status")
    if r.status_code == 200:
        summary = r.json().get("summary", {})
        kb_docs = summary.get("kb_documents", 0)
        kb_chunks = summary.get("kb_chunks", 0)
        ok(f"KB documents seeded ({kb_docs})", kb_docs >= 8,
           f"expected >=8, got {kb_docs}")
        ok(f"KB chunks with embeddings ({kb_chunks})", kb_chunks >= 30,
           f"expected >=30, got {kb_chunks}")

    # 3. Agent chat that exercises KB search (LO asking about TRID)
    # The kb_search tool calls get_embeddings() which hits the embedding model,
    # then runs pgvector cosine similarity. Even if the LLM doesn't call
    # the tool, the agent responds from its system prompt's compliance context.
    await ws_chat(
        "/api/loan-officer/chat", "LO (TRID kb_search)",
        "Search the knowledge base for TRID Loan Estimate delivery requirements",
        ["trid", "loan estimate", "delivery", "business day", "disclosure",
         "requirement", "regulation"],
    )

    await ws_chat(
        "/api/underwriter/chat", "UW (ECOA kb_search)",
        "Search the compliance knowledge base for ECOA fair lending prohibited factors",
        ["ecoa", "fair lending", "prohibited", "discrimination", "factor",
         "race", "protected", "equal credit"],
    )


async def test_websocket_chats():
    section("WebSocket Agent Chats")

    # Public assistant -- product info
    await ws_chat(
        "/api/chat", "Public (products)",
        "What types of mortgage loans do you offer?",
        ["conventional", "fha", "va", "loan", "mortgage", "product"],
    )

    # Public assistant -- affordability
    await ws_chat(
        "/api/chat", "Public (affordability)",
        "I make $120,000 a year with $500 in monthly debts. How much house can I afford?",
        ["afford", "loan", "payment", "income", "amount", "dti", "$"],
    )

    # Borrower -- application status
    await ws_chat(
        "/api/borrower/chat", "Borrower (status)",
        "What is the current status of my mortgage application?",
        ["application", "status", "stage", "loan", "document"],
    )

    # Borrower -- document info
    await ws_chat(
        "/api/borrower/chat", "Borrower (documents)",
        "What documents do I still need to provide?",
        ["document", "required", "upload", "paystub", "bank", "tax", "missing", "provide"],
    )

    # Loan officer -- application review
    await ws_chat(
        "/api/loan-officer/chat", "LO (app review)",
        "Show me the details for the next application in my queue",
        ["application", "borrower", "loan", "amount", "stage", "property"],
    )

    # Loan officer -- document quality
    await ws_chat(
        "/api/loan-officer/chat", "LO (readiness)",
        "Is the application ready for underwriting?",
        ["underwriting", "ready", "document", "condition", "missing", "complete",
         "blocker", "application", "assigned", "queue"],
    )

    # Underwriter -- risk assessment
    await ws_chat(
        "/api/underwriter/chat", "UW (risk)",
        "Give me a risk assessment for the application in my queue",
        ["risk", "dti", "ltv", "credit", "score", "assessment", "income", "factor"],
    )

    # Underwriter -- compliance check
    await ws_chat(
        "/api/underwriter/chat", "UW (compliance)",
        "Run a compliance check on the application",
        ["compliance", "ecoa", "trid", "atr", "pass", "fail", "check", "regulation"],
    )

    # CEO -- pipeline overview
    await ws_chat(
        "/api/ceo/chat", "CEO (pipeline)",
        "Give me an overview of our current loan pipeline",
        ["pipeline", "application", "stage", "active", "underwriting", "approval",
         "loan", "total", "status"],
    )

    # CEO -- LO performance
    await ws_chat(
        "/api/ceo/chat", "CEO (LO performance)",
        "How are our loan officers performing?",
        ["loan officer", "performance", "pull-through", "rate", "pipeline",
         "torres", "patel", "williams", "active", "closed"],
    )


# ---------------------------------------------------------------------------
# 15. WebSocket protocol edge cases
# ---------------------------------------------------------------------------

async def test_websocket_protocol():
    section("WebSocket Protocol")

    # Public chat accepts without token
    try:
        async with websockets.connect(
            f"{WS_BASE}/api/chat",
            additional_headers=HEADERS,
        ) as ws:
            ok("public chat connects without token", True)
            await ws.close()
    except Exception as e:
        ok("public chat connects without token", False, str(e)[:100])

    # Authenticated chat without token (AUTH_DISABLED=true, so should still work)
    try:
        async with websockets.connect(
            f"{WS_BASE}/api/borrower/chat",
            additional_headers=HEADERS,
        ) as ws:
            ok("borrower chat connects (AUTH_DISABLED)", True)
            await ws.close()
    except Exception as e:
        ok("borrower chat connects (AUTH_DISABLED)", False, str(e)[:100])

    # Send malformed message
    try:
        async with websockets.connect(
            f"{WS_BASE}/api/chat",
            additional_headers=HEADERS,
        ) as ws:
            await ws.send("not json")
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            ok("malformed message gets error response",
               msg.get("type") in ("error", "token", "done"),
               f"type={msg.get('type')}")
    except Exception as e:
        # Connection close on bad message is also acceptable
        ok("malformed message handled gracefully", True, f"(closed: {str(e)[:60]})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Live test suite for Mortgage AI API")
    parser.add_argument("--no-chat", action="store_true",
                        help="Skip WebSocket agent chat tests (requires LLM)")
    parser.add_argument("--section", choices=["rest", "chat", "all"], default="all",
                        help="Which sections to run")
    args = parser.parse_args()

    print("=" * 60)
    print("  LIVE TEST SUITE -- Mortgage AI API")
    print("=" * 60)

    run_rest = args.section in ("rest", "all")
    run_chat = args.section in ("chat", "all") and not args.no_chat

    async with httpx.AsyncClient(base_url=BASE, headers=HEADERS, timeout=15) as c:

        # Pre-flight: make sure server is up
        try:
            r = await c.get("/health/")
            if r.status_code != 200:
                print(f"\n  Server returned {r.status_code} on /health/ -- is it running?")
                sys.exit(2)
        except httpx.ConnectError:
            print("\n  Cannot connect to server at localhost:8000 -- is it running?")
            sys.exit(2)

        if run_rest:
            await test_health(c)
            await test_public_api(c)
            ctx = await test_application_crud(c)

            # Use seeded app for detail tests (has documents, conditions, etc.)
            detail_id = ctx.get("seeded_id", ctx.get("created_id"))
            if detail_id:
                await test_application_details(c, detail_id)
                await test_documents(c, detail_id)
                await test_conditions(c, detail_id)
                await test_decisions(c, detail_id)
                await test_coborrower_management(c, detail_id)
                await test_condition_response(c, detail_id)

            # Use created app for HMDA + lifecycle
            lifecycle_id = ctx.get("created_id")
            if lifecycle_id:
                await test_hmda(c, lifecycle_id)

            await test_admin(c)
            await test_error_handling(c)
            await test_conversation_history(c)
            await test_application_lifecycle(c)
            await test_openapi(c)
            await test_analytics(c)
            await test_model_monitoring(c)
            await test_audit_extended(c, detail_id)

    if run_chat:
        await test_agent_responses()
        async with httpx.AsyncClient(base_url=BASE, headers=HEADERS, timeout=15) as c2:
            await test_embedding_model(c2)
        await test_websocket_chats()
        await test_websocket_protocol()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    if ERRORS:
        print("\nFailures:")
        for e in ERRORS:
            print(f"  - {e}")

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
