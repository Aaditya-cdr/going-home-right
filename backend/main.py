from __future__ import annotations

from typing import Any
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ai_adapter import ai_adapter
from dataset import get_test_case_by_id, get_test_cases
from models import (
    AnalyzeRequest,
    AuditOutputRequest,
    DischargeAnalysisResponse,
    SafetyFlag,
    TestCaseInfo,
)
from pdf_parser import extract_text_from_pdf

app = FastAPI(
    title="AAYU 2026 — Going Home Right API",
    description="Evidence-Linked Discharge Care Companion: source-linked extraction, safety checks, and teach-back comprehension.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "Going Home Right — Evidence-Linked Discharge Care Companion API",
        "version": "0.2.0",
        "hackathon": "AAYU 2026",
        "problem_statement": "T03 — Going Home Right",
        "status": "online",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "test_cases": "/test-cases",
            "analyze": "/analyze",
            "upload": "/upload",
            "audit_output": "/audit-output",
        },
        "disclaimer": "Synthetic demo for hackathon evaluation only. Not a medical device or product.",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "synthetic-demo-companion",
        "llm_configured": ai_adapter.is_llm_available,
        "provider": ai_adapter.provider_name,
    }


@app.get("/sample")
def sample():
    cases = get_test_cases()
    return {"text": cases[0]["source_text"] if cases else ""}


@app.get("/test-cases", response_model=list[TestCaseInfo])
def list_test_cases():
    return get_test_cases()


@app.get("/test-cases/{case_id}", response_model=TestCaseInfo)
def get_test_case(case_id: str):
    case = get_test_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Test case '{case_id}' not found.")
    return case


@app.post("/analyze", response_model=DischargeAnalysisResponse)
def analyze_endpoint(request: AnalyzeRequest):
    return ai_adapter.analyze(request.text, test_case_id=request.test_case_id)


@app.post("/upload", response_model=DischargeAnalysisResponse)
async def upload_endpoint(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    content = await file.read(5_000_001)

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="File too large (5 MB maximum).")

    if filename.endswith(".txt"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="Text file must use UTF-8 encoding.") from exc
    elif filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    else:
        raise HTTPException(status_code=415, detail="Unsupported format. Please upload a .txt or text-based .pdf.")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Uploaded document contains no readable text.")

    res = ai_adapter.analyze(text)
    res.source_text = text
    return res


@app.post("/audit-output", response_model=list[SafetyFlag])
def audit_output_endpoint(request: AuditOutputRequest):
    """Safety audit that verifies candidate medications against source text to flag hallucinations."""
    return ai_adapter.audit_candidate_plan(request.source_text, request.candidate_medications)
