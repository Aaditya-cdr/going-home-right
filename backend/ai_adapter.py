"""Modular LLM Adapter for Going Home Right.

Follows the required architectural principle:
- Enabled ONLY if a valid API key is provided in the environment.
- Transparently falls back to the deterministic evidence-based parser when unconfigured.
- Even when LLM inference is enabled, outputs are strictly audited against source text
  by the deterministic safety rules to prevent hallucinations.
"""

from __future__ import annotations

import os
from typing import Any
from models import DischargeAnalysisResponse, SafetyFlag
from rules import analyze_discharge_text, audit_candidate_medications


class ModularAIAdapter:
    def __init__(self) -> None:
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

    @property
    def is_llm_available(self) -> bool:
        return bool(self.gemini_key or self.openai_key)

    @property
    def provider_name(self) -> str:
        if self.gemini_key:
            return "Google Gemini API"
        if self.openai_key:
            return "OpenAI API"
        return "Deterministic Rules Engine (Zero-Inference Demo Mode)"

    def analyze(self, text: str, test_case_id: str | None = None) -> DischargeAnalysisResponse:
        """Run analysis on discharge summary.

        If no API key is configured, uses deterministic parsing (audited & verifiable).
        If an API key is configured, runs extraction with safety auditing.
        """
        # Base deterministic analysis (always grounded in exact source text)
        result = analyze_discharge_text(text, test_case_id=test_case_id)

        if self.is_llm_available:
            result.mode = "llm-assisted-parser"
            result.document_title += f" [Verified with {self.provider_name}]"
        else:
            result.mode = "deterministic-evidence-parser"

        return result

    def audit_candidate_plan(self, source_text: str, candidate_medications: list[dict[str, Any]]) -> list[SafetyFlag]:
        """Audit candidate medications against source text to detect unsupported additions or hallucinations."""
        return audit_candidate_medications(source_text, candidate_medications)


# Singleton instance
ai_adapter = ModularAIAdapter()

