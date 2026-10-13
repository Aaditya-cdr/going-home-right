from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class MedicationItem(BaseModel):
    name: str = Field(description="Generic or brand name of medication")
    strength: Optional[str] = Field(default=None, description="e.g., 500 mg, 10 mcg")
    dose: Optional[str] = Field(default=None, description="e.g., 1 tablet, 2 puffs")
    route: Optional[str] = Field(default=None, description="e.g., by mouth, oral, topical")
    frequency: Optional[str] = Field(default=None, description="e.g., 3 times daily, once daily")
    timing_slot: Literal["morning", "afternoon", "night", "as_needed", "unspecified"] = Field(
        default="unspecified",
        description="Organized into morning/afternoon/night ONLY when explicitly stated in source"
    )
    duration: Optional[str] = Field(default=None, description="e.g., for 5 days, for 2 weeks")
    raw_text: str = Field(description="Cleaned line text")
    source_passage: str = Field(description="Exact source quotation from document")
    status: Literal["documented", "review", "unsupported"] = "documented"
    review_reasons: list[str] = Field(default_factory=list)
    # Patient-friendly bilingual fields
    patient_summary_en: str = Field(default="", description="Plain English conversational explanation")
    patient_summary_hi: str = Field(default="", description="Conversational Hindi explanation")
    safety_alert_en: Optional[str] = Field(default=None, description="Plain English safety flag if incomplete")
    safety_alert_hi: Optional[str] = Field(default=None, description="Conversational Hindi safety flag if incomplete")


class FollowUpItem(BaseModel):
    provider_or_clinic: str
    timing: Optional[str] = Field(default=None, description="Timing, date, or interval stated in document")
    contact: Optional[str] = Field(default=None, description="Phone number or scheduling contact")
    actions: list[str] = Field(default_factory=list)
    prep_instructions: list[str] = Field(default_factory=list, description="Explicit preparation steps like fasting or bringing logs")
    raw_text: str
    source_passage: str
    status: Literal["documented", "review"] = "documented"
    review_reasons: list[str] = Field(default_factory=list)
    # Patient-friendly bilingual fields
    patient_summary_en: str = Field(default="")
    patient_summary_hi: str = Field(default="")
    timing_missing: bool = Field(default=False)
    timing_alert_en: Optional[str] = Field(default=None)
    timing_alert_hi: Optional[str] = Field(default=None)


class WarningSignItem(BaseModel):
    sign: str
    action: str = Field(description="Action to take, e.g., call care team or go to emergency room")
    severity: Literal["urgent_emergency", "care_team_call"] = "care_team_call"
    raw_text: str
    source_passage: str
    patient_summary_en: str = Field(default="")
    patient_summary_hi: str = Field(default="")


class CareInstructionItem(BaseModel):
    category: str = Field(description="e.g., Wound care, Diet, Physical Activity, General")
    instruction: str
    raw_text: str
    source_passage: str
    status: Literal["documented", "review"] = "documented"
    review_reasons: list[str] = Field(default_factory=list)
    patient_summary_en: str = Field(default="")
    patient_summary_hi: str = Field(default="")


class SafetyFlag(BaseModel):
    flag_id: str
    category: Literal[
        "missing_critical_field",
        "conflicting_instructions",
        "unsupported_addition",
        "ambiguous_abbreviation",
        "missing_timing",
        "source_unverified",
        "general_review"
    ]
    severity: Literal["critical", "warning", "info"] = "warning"
    title: str
    message: str
    source_passage: Optional[str] = None
    action_required: str


class UnderstandingQuestion(BaseModel):
    id: str
    question: str
    question_hi: str = Field(default="")
    options: list[str]
    options_hi: list[str] = Field(default_factory=list)
    correct_index: int
    explanation: str
    explanation_hi: str = Field(default="")
    source_passage: str
    is_ambiguous: bool = False
    verification_note: Optional[str] = None


class ScheduleGroup(BaseModel):
    morning: list[MedicationItem] = Field(default_factory=list)
    afternoon: list[MedicationItem] = Field(default_factory=list)
    night: list[MedicationItem] = Field(default_factory=list)
    as_needed: list[MedicationItem] = Field(default_factory=list)
    documented_frequency: list[MedicationItem] = Field(default_factory=list)


class DischargeAnalysisResponse(BaseModel):
    mode: Literal["deterministic-evidence-parser", "llm-assisted-parser"] = "deterministic-evidence-parser"
    document_title: str = "Discharge Summary (Synthetic Demo)"
    source_text: str = Field(default="", description="Complete extracted source text of the document")
    ai_patient_overview: Optional[str] = Field(
        default=None,
        description="Plain-language patient overview synthesized by Gemini from documented instructions when configured"
    )
    medications: list[MedicationItem] = Field(default_factory=list)
    follow_ups: list[FollowUpItem] = Field(default_factory=list)
    warning_signs: list[WarningSignItem] = Field(default_factory=list)
    care_instructions: list[CareInstructionItem] = Field(default_factory=list)
    schedule: ScheduleGroup = Field(default_factory=ScheduleGroup)
    safety_flags: list[SafetyFlag] = Field(default_factory=list)
    teach_back: list[UnderstandingQuestion] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    disclaimer: str = (
        "SYNTHETIC HACKATHON PROTOTYPE ONLY: This software organizes documented text with exact source traceability. "
        "It does not diagnose, prescribe, or give medical advice. If any instruction is missing, unclear, or conflicting, "
        "always confirm with a healthcare provider."
    )


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    test_case_id: Optional[str] = None


class AuditOutputRequest(BaseModel):
    source_text: str = Field(min_length=1)
    candidate_medications: list[dict] = Field(default_factory=list)


class TestCaseInfo(BaseModel):
    id: str
    title: str
    description: str
    edge_case_type: str
    source_text: str
    expected_flags: list[str]
    simulated_hallucination: Optional[dict] = None
