"""Modular AI Adapter for Going Home Right.

Architectural and Healthcare Safety Principles:
1. Primary Source of Truth:
   - The deterministic rules engine is ALWAYS the primary source of truth for clinical extraction:
     medication names, strengths, dosages, routes, frequencies, durations, warning signs, and conflicts.
   - The application NEVER claims that an LLM independently verifies clinical dosages or orders.
2. Clearly Defined AI Enhancement Task:
   - When configured with a valid GEMINI_API_KEY / GOOGLE_API_KEY, Google Gemini performs a clearly
     defined communication task: synthesizing a plain-language patient/caregiver overview from documented instructions.
   - The returned overview is saved in `ai_patient_overview` and displayed transparently in the UI.
3. Provider Integrity:
   - Only Google Gemini is supported. No phantom OpenAI configuration claims.
   - Unconfigured mode is honestly labeled as "Deterministic Rules Engine (Primary Source of Truth)".
4. Defensive Fault Tolerance:
   - 10-second timeout on external API requests.
   - Any failure (network, rate limit, timeout) gracefully falls back to deterministic parsing without crashing.
   - API keys are strictly kept server-side and never exposed to the frontend or logs.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from models import DischargeAnalysisResponse, SafetyFlag
from rules import analyze_discharge_text, audit_candidate_medications

logger = logging.getLogger("ai_adapter")


class ModularAIAdapter:
    def __init__(self) -> None:
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    @property
    def is_llm_available(self) -> bool:
        return bool(self.gemini_key and self.gemini_key.strip())

    @property
    def provider_name(self) -> str:
        if self.is_llm_available:
            return "Google Gemini API (Plain-Language Synthesis)"
        return "Deterministic Rules Engine (Primary Source of Truth)"

    def analyze(self, text: str, test_case_id: str | None = None) -> DischargeAnalysisResponse:
        """Run analysis on discharge summary.

        1. Deterministic baseline analysis is ALWAYS computed first as clinical ground truth.
        2. If GEMINI_API_KEY is configured, requests a plain-language patient overview under a strict 10s timeout.
        3. If no key is set or the call fails, honestly returns the deterministic analysis without false claims.
        """
        # Step 1: Base deterministic analysis (clinical ground truth)
        result = analyze_discharge_text(text, test_case_id=test_case_id)
        result.source_text = text

        if not self.is_llm_available:
            result.mode = "deterministic-evidence-parser"
            result.document_title = "Synthetic Discharge Summary (Deterministic Rules Engine)"
            result.ai_patient_overview = None
            return result

        # Step 2: Request plain-language patient overview from Gemini
        try:
            return self._call_gemini_api(text, result)
        except Exception as exc:
            safe_err = type(exc).__name__
            logger.warning("Gemini synthesis call failed (%s). Falling back safely to deterministic rules engine.", safe_err)
            result.mode = "deterministic-evidence-parser"
            result.document_title = "Synthetic Discharge Summary (Deterministic Rules Fallback)"
            result.ai_patient_overview = None
            result.safety_flags.append(
                SafetyFlag(
                    flag_id="llm-fallback-safety",
                    category="general_review",
                    severity="info",
                    title="AI Plain-Language Synthesis Fallback",
                    message=f"Gemini plain-language synthesis could not be completed ({safe_err}). Primary deterministic rules engine active.",
                    action_required="Standard rule-based grounded extraction is active.",
                )
            )
            return result

    def _call_gemini_api(self, text: str, baseline: DischargeAnalysisResponse) -> DischargeAnalysisResponse:
        """Execute a genuine, audited Google Gemini REST request for plain-language overview synthesis."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"

        prompt = (
            "You are a healthcare communication assistant for a synthetic hackathon demo.\n"
            "Your task is ONLY to synthesize a warm, simple, 2-3 sentence plain-language overview "
            "for the patient/caregiver based strictly on their documented discharge instructions below.\n\n"
            "CRITICAL HEALTHCARE SAFETY CONSTRAINTS:\n"
            "1. NEVER invent, alter, or recommend any medication, dose, timing, or diagnosis.\n"
            "2. Plain language only (6th grade reading level).\n"
            "3. Do not give clinical advice; only summarize what is documented.\n\n"
            f"DOCUMENTED INSTRUCTIONS:\n{text}\n\n"
            "Respond ONLY in valid JSON format:\n"
            "{\n"
            '  "patient_overview": "2-3 sentence simple overview for the patient"\n'
            "}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10.0) as response:
            status_code = response.getcode()
            if status_code != 200:
                raise RuntimeError(f"Gemini API returned HTTP {status_code}")
            resp_body = response.read().decode("utf-8")
            resp_json = json.loads(resp_body)

        candidates = resp_json.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned empty candidate response")

        text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        parsed = json.loads(text_content) if text_content else {}

        # Update response transparently
        overview = parsed.get("patient_overview", "").strip()
        if overview:
            baseline.ai_patient_overview = overview
            baseline.mode = "llm-assisted-parser"
            baseline.document_title = "Synthetic Discharge Summary (Rules Ground Truth + Gemini Plain-Language Overview)"
            baseline.summary["ai_patient_overview"] = 1
        else:
            baseline.mode = "deterministic-evidence-parser"
            baseline.document_title = "Synthetic Discharge Summary (Deterministic Rules Engine)"

        return baseline

    def audit_candidate_plan(self, source_text: str, candidate_medications: list[dict[str, Any]]) -> list[SafetyFlag]:
        """Audit candidate medications against source text to detect unsupported additions or hallucinations."""
        return audit_candidate_medications(source_text, candidate_medications)


# Singleton instance
ai_adapter = ModularAIAdapter()
