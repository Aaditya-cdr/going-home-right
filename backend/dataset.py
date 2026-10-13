"""Synthetic Dataset for AAYU 2026 - Going Home Right.

Contains 10 fictional test cases covering baseline complete instructions and key safety edge cases:
1. Complete discharge instructions (clean baseline)
2. Missing medication dose
3. Missing medication frequency
4. Missing duration
5. Conflicting timings
6. Documented follow-up appointment
7. Documented warning signs
8. Unsupported medication addition in generated output (hallucination audit)
9. Ambiguous abbreviation (ISMP Do Not Use list)
10. Multiple medications requiring explicit schedule grouping
"""

from typing import Any

SYNTHETIC_TEST_CASES: list[dict[str, Any]] = [
    {
        "id": "case-1-complete",
        "title": "Case 1: Complete Discharge Instructions (Baseline)",
        "description": "Comprehensive discharge plan with clear doses, routes, frequencies, durations, follow-up contact, and warning signs.",
        "edge_case_type": "complete_instructions",
        "expected_flags": [],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Jane Doe (Fictional Patient #101)
Discharge Date: October 14, 2026

MEDICATIONS
- Amoxicillin 500 mg: take 1 capsule by mouth 3 times daily for 7 days.
- Lisinopril 10 mg: take 1 tablet by mouth once daily in the morning for hypertension.
- Acetaminophen 650 mg: take 1 tablet by mouth every 6 hours as needed for mild pain.

FOLLOW-UP
- Schedule appointment with Dr. Sarah Smith at Oak Clinic in 7 days. Call (555) 0123.
- Lab test: Comprehensive metabolic panel in 14 days at City Lab.

WARNING SIGNS
- Seek urgent emergency care for difficulty breathing, chest pain, or sudden dizziness.
- Call your care team within 24 hours for fever above 38.5°C or increasing redness around incision.

CARE INSTRUCTIONS
- Keep surgical dressing dry and clean for 48 hours.
- Drink at least 2 liters of water daily.
- Avoid lifting objects heavier than 10 lbs for 2 weeks.
""",
    },
    {
        "id": "case-2-missing-dose",
        "title": "Case 2: Missing Medication Dose",
        "description": "Medication line prescribes Lisinopril without specifying the dose/strength quantity.",
        "edge_case_type": "missing_dose",
        "expected_flags": ["Missing medication dose or strength for Lisinopril"],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: John Smith (Fictional Patient #102)

MEDICATIONS
- Lisinopril: take 1 tablet by mouth once daily in the morning.
- Metformin 500 mg: take 1 tablet by mouth twice daily with meals.

FOLLOW-UP
- Primary care follow-up in 10 days. Call (555) 0144 to schedule.

WARNING SIGNS
- Call care team for blood pressure readings above 160/100 or persistent lightheadedness.

CARE INSTRUCTIONS
- Record blood pressure twice daily in a home log.
""",
    },
    {
        "id": "case-3-missing-frequency",
        "title": "Case 3: Missing Medication Frequency",
        "description": "Prescription for Amoxicillin provides strength and duration but omits how often to take it per day.",
        "edge_case_type": "missing_frequency",
        "expected_flags": ["Missing frequency or daily interval for Amoxicillin"],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Emily Davis (Fictional Patient #103)

MEDICATIONS
- Amoxicillin 500 mg: take 1 capsule by mouth for 10 days.
- Ibuprofen 400 mg: take 1 tablet by mouth twice daily with food as needed.

FOLLOW-UP
- Return to ENT clinic in 14 days. Call (555) 0188.

WARNING SIGNS
- Seek emergency care if facial swelling or difficulty swallowing occurs.
- Call doctor if fever exceeds 38°C.
""",
    },
    {
        "id": "case-4-missing-duration",
        "title": "Case 4: Missing Duration for Course",
        "description": "Prednisone taper/course has strength and frequency but omits duration, risking prolonged steroid use.",
        "edge_case_type": "missing_duration",
        "expected_flags": ["Missing course duration or stop date for Prednisone"],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Michael Brown (Fictional Patient #104)

MEDICATIONS
- Prednisone 20 mg: take 1 tablet by mouth once daily in the morning with food.
- Albuterol inhaler 90 mcg: inhale 2 puffs every 4 to 6 hours as needed for shortness of breath.

FOLLOW-UP
- Pulmonary clinic in 7 days. Call (555) 0211.

WARNING SIGNS
- Seek immediate emergency care for severe wheezing unresponsive to inhaler.
- Call clinic for jitteriness or rapid heartbeat.
""",
    },
    {
        "id": "case-5-conflicting-timings",
        "title": "Case 5: Conflicting Timings / Instructions",
        "description": "Contains contradictory instructions for Metformin in two different lines of the same summary.",
        "edge_case_type": "conflicting_instructions",
        "expected_flags": ["Conflicting instructions detected for Metformin"],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Robert Taylor (Fictional Patient #105)

MEDICATIONS
- Metformin 500 mg: take 1 tablet by mouth twice daily with meals.
- Atorvastatin 20 mg: take 1 tablet by mouth once daily at bedtime.
- Metformin 500 mg: take 1 tablet by mouth once daily at bedtime only.

FOLLOW-UP
- Endocrinology clinic in 2 weeks. Call (555) 0320.

WARNING SIGNS
- Call care team for blood glucose below 70 mg/dL or above 250 mg/dL.
- Seek emergency care for confusion, nausea, or rapid breathing.
""",
    },
    {
        "id": "case-6-follow-up",
        "title": "Case 6: Documented Follow-up Appointment",
        "description": "Tests detailed extraction of structured follow-up timing, provider, clinic contact, and preparatory steps.",
        "edge_case_type": "documented_followup",
        "expected_flags": [],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Clara Wilson (Fictional Patient #106)

MEDICATIONS
- Hydrochlorothiazide 25 mg: take 1 tablet by mouth once daily in the morning.

FOLLOW-UP
- Appointment confirmed with Dr. Robert Example at Metro Cardiology on October 22, 2026 at 10:00 AM.
- Call (555) 0123 to reschedule or if transportation assistance is required.
- Bring all current medication bottles and your blood pressure log.

WARNING SIGNS
- Call doctor for dizziness upon standing or calf cramps.
- Seek emergency care for chest pressure.
""",
    },
    {
        "id": "case-7-warning-signs",
        "title": "Case 7: Documented Warning Signs (Triage Split)",
        "description": "Tests categorization between immediate emergency symptoms versus routine care-team notifications.",
        "edge_case_type": "warning_signs",
        "expected_flags": [],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: David Miller (Fictional Patient #107)

MEDICATIONS
- Cephalexin 500 mg: take 1 capsule by mouth 4 times daily for 7 days.

FOLLOW-UP
- Wound check in 5 days. Call (555) 0455.

WARNING SIGNS
- EMERGENCY: Call 911 or go to nearest emergency room immediately for chest pain, sudden numbness in face or arms, or coughing up blood.
- CARE TEAM: Call the clinic at (555) 0455 if temperature is above 38.0°C, wound drainage increases, or surrounding redness spreads.
""",
    },
    {
        "id": "case-8-unsupported-addition",
        "title": "Case 8: Unsupported Medication Addition (Safety Audit)",
        "description": "Simulates an unverified or hallucinated output where a candidate plan includes Oxycodone 5 mg not documented in the source.",
        "edge_case_type": "unsupported_addition",
        "expected_flags": ["CRITICAL: Unsupported medication 'Oxycodone' added without source documentation"],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Laura Martinez (Fictional Patient #108)

MEDICATIONS
- Acetaminophen 500 mg: take 1 tablet by mouth every 6 hours as needed for mild pain.

FOLLOW-UP
- Follow-up with primary care in 14 days. Call (555) 0677.

WARNING SIGNS
- Call care team if pain becomes severe or unmanageable.
""",
        "simulated_hallucination": {
            "name": "Oxycodone",
            "strength": "5 mg",
            "dose": "1 tablet",
            "route": "by mouth",
            "frequency": "every 4 hours as needed",
            "timing_slot": "as_needed",
            "duration": "for 3 days",
            "raw_text": "Oxycodone 5 mg: take 1 tablet by mouth every 4 hours as needed for severe pain.",
            "source_passage": "Not found in source document — potential AI hallucination",
            "status": "unsupported",
            "review_reasons": ["CRITICAL: This medication does not exist anywhere in the source document!"]
        }
    },
    {
        "id": "case-9-ambiguous-abbreviation",
        "title": "Case 9: Ambiguous Abbreviations (ISMP 'Do Not Use' List)",
        "description": "Contains error-prone clinical abbreviations ('MS', 'QD', 'U') that require explicit human review.",
        "edge_case_type": "ambiguous_abbreviations",
        "expected_flags": [
            "Ambiguous abbreviation 'MS' detected (may mean Morphine Sulfate or Magnesium Sulfate)",
            "Ambiguous abbreviation 'QD' detected (easily confused with QID or QOD)",
            "Ambiguous abbreviation 'U' detected (easily confused with zero)"
        ],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: George Harris (Fictional Patient #109)

MEDICATIONS
- MS 10 mg QD PO for severe pain.
- Regular Insulin 5 U subcutaneous before meals.
- Pain medicine: take PRN as directed.

FOLLOW-UP
- Follow-up in 1 week.

WARNING SIGNS
- Call doctor if extreme drowsiness or low blood sugar occurs.
""",
    },
    {
        "id": "case-10-multiple-meds",
        "title": "Case 10: Multiple Medications & Strict Time Slots",
        "description": "Complex regimen with morning, lunch, and bedtime timings explicitly stated, demonstrating schedule separation without guessing.",
        "edge_case_type": "multiple_medications_schedule",
        "expected_flags": [],
        "source_text": """DISCHARGE SUMMARY — SYNTHETIC DEMO
Patient: Margaret Clark (Fictional Patient #110)

MEDICATIONS
- Levothyroxine 50 mcg: take 1 tablet by mouth once daily in the morning 30 minutes before breakfast.
- Furosemide 20 mg: take 1 tablet by mouth once daily with lunch in the afternoon.
- Metoprolol Tartrate 25 mg: take 1 tablet by mouth twice daily with meals.
- Atorvastatin 40 mg: take 1 tablet by mouth once daily at bedtime.
- Nitroglycerin 0.4 mg: place 1 tablet under the tongue every 5 minutes as needed for chest pain up to 3 doses.

FOLLOW-UP
- Cardiology clinic visit in 10 days. Call (555) 0890.
- Check electrolyte panel in 7 days at outpatient lab.

WARNING SIGNS
- Seek emergency care immediately if chest pain is not relieved after 1 dose of nitroglycerin.
- Call clinic for sudden weight gain of more than 3 lbs in 24 hours.

CARE INSTRUCTIONS
- Low sodium diet (under 2,000 mg daily).
- Weigh yourself every morning after urinating and before breakfast.
""",
    },
]


def get_test_cases() -> list[dict[str, Any]]:
    return SYNTHETIC_TEST_CASES


def get_test_case_by_id(case_id: str) -> dict[str, Any] | None:
    return next((c for c in SYNTHETIC_TEST_CASES if c["id"] == case_id), None)

