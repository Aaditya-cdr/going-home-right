"""Automated Test Suite for Going Home Right (AAYU 2026).

Covers:
1. All 10 synthetic clinical edge cases (deterministic rules engine).
2. End-to-end API workflows (uploads, PDF selectable text, empty/malformed files, unsupported types).
3. Healthcare safety audits (hallucination defense, missing fields, conflicting instructions).
4. Genuine source-text preservation and honest AI adapter labeling.
"""

from __future__ import annotations

import io
import pymupdf
from fastapi.testclient import TestClient

from ai_adapter import ai_adapter
from dataset import get_test_cases
from main import app
from rules import analyze_discharge_text, audit_candidate_medications


def run_tests() -> bool:
    print("=====================================================================")
    print(" RUNNING AAYU 2026 'GOING HOME RIGHT' COMPREHENSIVE TEST SUITE")
    print("=====================================================================")

    client = TestClient(app)
    cases = {c["id"]: c for c in get_test_cases()}

    # -------------------------------------------------------------
    # 1. Ten Synthetic Clinical Edge Cases (Rules Engine)
    # -------------------------------------------------------------
    # Test 1: Complete baseline
    c1 = cases["case-1-complete"]
    res1 = analyze_discharge_text(c1["source_text"])
    critical1 = [f for f in res1.safety_flags if f.severity == "critical"]
    assert len(critical1) == 0, f"Case 1 had unexpected critical flags: {critical1}"
    assert len(res1.medications) >= 3, "Case 1 should extract 3 medications"
    assert len(res1.follow_ups) >= 1, "Case 1 should extract follow-up"
    assert len(res1.warning_signs) >= 2, "Case 1 should extract warning signs"
    print("[PASS] Scenario 1 (Case 1): Complete instructions baseline parsed cleanly with 0 critical flags.")

    # Test 2: Missing dose
    c2 = cases["case-2-missing-dose"]
    res2 = analyze_discharge_text(c2["source_text"])
    has_dose_flag = any("Missing Dose for Lisinopril" in f.title for f in res2.safety_flags)
    assert has_dose_flag, f"Case 2 failed to flag missing dose for Lisinopril: {[f.title for f in res2.safety_flags]}"
    print("[PASS] Scenario 2 (Case 2): Missing dose for Lisinopril correctly identified and flagged.")

    # Test 3: Missing frequency
    c3 = cases["case-3-missing-frequency"]
    res3 = analyze_discharge_text(c3["source_text"])
    has_freq_flag = any("Missing Frequency for Amoxicillin" in f.title for f in res3.safety_flags)
    assert has_freq_flag, f"Case 3 failed to flag missing frequency for Amoxicillin: {[f.title for f in res3.safety_flags]}"
    print("[PASS] Scenario 3 (Case 3): Missing frequency for Amoxicillin correctly identified and flagged.")

    # Test 4: Missing duration
    c4 = cases["case-4-missing-duration"]
    res4 = analyze_discharge_text(c4["source_text"])
    has_dur_flag = any("Missing Duration for Prednisone" in f.title for f in res4.safety_flags)
    assert has_dur_flag, f"Case 4 failed to flag missing duration for Prednisone: {[f.title for f in res4.safety_flags]}"
    print("[PASS] Scenario 4 (Case 4): Missing course duration for Prednisone correctly flagged.")

    # Test 5: Conflicting instructions
    c5 = cases["case-5-conflicting-timings"]
    res5 = analyze_discharge_text(c5["source_text"])
    has_conflict = any("Conflicting Instructions for Metformin" in f.title for f in res5.safety_flags)
    assert has_conflict, f"Case 5 failed to flag contradictory Metformin directions: {[f.title for f in res5.safety_flags]}"
    print("[PASS] Scenario 5 (Case 5): Contradictory Metformin instructions preserved and flagged for human review.")

    # Test 6: Documented follow-up appointment & prep instructions
    c6 = cases["case-6-follow-up"]
    res6 = analyze_discharge_text(c6["source_text"])
    has_timing = any(f.timing and "October 22, 2026" in f.timing for f in res6.follow_ups)
    has_contact = any(f.contact and "0123" in f.contact for f in res6.follow_ups)
    assert has_timing, f"Case 6 did not capture appointment timing: {[f.timing for f in res6.follow_ups]}"
    assert has_contact, f"Case 6 did not capture phone contact: {[f.contact for f in res6.follow_ups]}"
    has_prep = any(any("bottles" in p.lower() for p in f.prep_instructions) for f in res6.follow_ups)
    assert has_prep, "Case 6 failed to associate prep instructions"
    has_false_missing_timing = any(f.category == "missing_timing" for f in res6.safety_flags)
    assert not has_false_missing_timing, f"Case 6 generated false-positive missing timing flags: {[f.title for f in res6.safety_flags]}"
    print("[PASS] Scenario 6 (Case 6): Documented follow-up timing extracted; prep steps NOT misclassified as missing timing.")

    # Test 7: Warning signs triage
    c7 = cases["case-7-warning-signs"]
    res7 = analyze_discharge_text(c7["source_text"])
    emergency_signs = [w for w in res7.warning_signs if w.severity == "urgent_emergency"]
    routine_signs = [w for w in res7.warning_signs if w.severity == "care_team_call"]
    assert len(emergency_signs) >= 1, "Case 7 should have emergency signs"
    assert len(routine_signs) >= 1, "Case 7 should have routine call signs"
    print("[PASS] Scenario 7 (Case 7): Warning signs partitioned into emergency triage vs care-team calls.")

    # Test 8: Unsupported medication addition (hallucination defense)
    c8 = cases["case-8-unsupported-addition"]
    simulated = [c8["simulated_hallucination"]]
    audit_flags = audit_candidate_medications(c8["source_text"], simulated)
    assert len(audit_flags) > 0, "Case 8 should catch unsupported Oxycodone addition"
    assert "Oxycodone" in audit_flags[0].title, f"Case 8 flag mismatch: {audit_flags[0].title}"
    print("[PASS] Scenario 8 (Case 8): Safety audit caught unsupported medication addition (hallucination guard active).")

    # Test 9: Ambiguous abbreviations (ISMP Do Not Use list)
    c9 = cases["case-9-ambiguous-abbreviation"]
    res9 = analyze_discharge_text(c9["source_text"])
    flag_titles = [f.title for f in res9.safety_flags]
    assert any("MS" in t for t in flag_titles) and any("QD" in t for t in flag_titles) and any("Units" in t or "U" in t for t in flag_titles)
    print("[PASS] Scenario 9 (Case 9): ISMP error-prone abbreviations ('MS', 'QD', 'U') detected and flagged.")

    # Test 10: Multiple medications strict time slots
    c10 = cases["case-10-multiple-meds"]
    res10 = analyze_discharge_text(c10["source_text"])
    assert len(res10.schedule.morning) >= 1 and len(res10.schedule.afternoon) >= 1 and len(res10.schedule.night) >= 1
    assert res10.schedule.morning[0].name.startswith("Levothyroxine")
    assert res10.schedule.afternoon[0].name.startswith("Furosemide")
    assert res10.schedule.night[0].name.startswith("Atorvastatin")
    print("[PASS] Scenario 10 (Case 10): Multiple medications parsed into documented time slots without guessing.")

    # -------------------------------------------------------------
    # 2. Workflow & Endpoint Integration Tests
    # -------------------------------------------------------------
    # Scenario 11: Valid text-based discharge summary via /analyze
    r_analyze = client.post("/analyze", json={"text": c1["source_text"]})
    assert r_analyze.status_code == 200, f"/analyze failed: {r_analyze.status_code}"
    data_analyze = r_analyze.json()
    assert data_analyze["source_text"] == c1["source_text"], "Source text not preserved in /analyze response"
    print("[PASS] Scenario 11: Valid text-based summary analyzed via /analyze with source text preserved.")

    # Scenario 12: Valid PDF with selectable text via /upload
    doc = pymupdf.open()
    page = doc.new_page()
    pdf_sample_text = (
        "DISCHARGE SUMMARY — HOSPITAL CLINIC\n"
        "MEDICATIONS\n"
        "- Metformin 500 mg: take 1 tablet by mouth twice daily with meals.\n"
        "FOLLOW-UP\n"
        "- Primary care follow-up in 14 days. Call (555) 0199.\n"
        "WARNING SIGNS\n"
        "- Call care team for blood glucose above 250 mg/dL.\n"
    )
    page.insert_text((50, 72), pdf_sample_text)
    pdf_bytes = doc.tobytes()
    doc.close()

    r_pdf = client.post("/upload", files={"file": ("discharge_test.pdf", pdf_bytes, "application/pdf")})
    assert r_pdf.status_code == 200, f"PDF upload failed: {r_pdf.status_code} {r_pdf.text}"
    pdf_data = r_pdf.json()
    assert "Metformin" in pdf_data["source_text"], "PDF selectable text not extracted or preserved"
    assert len(pdf_data["medications"]) >= 1, "Medications not extracted from valid PDF"
    print("[PASS] Scenario 12: Valid PDF with selectable text uploaded and parsed via PyMuPDF.")

    # Scenario 13: Empty file upload (0 bytes) -> HTTP 400
    r_empty = client.post("/upload", files={"file": ("empty.txt", b"", "text/plain")})
    assert r_empty.status_code == 400, f"Expected 400 for empty file, got {r_empty.status_code}"
    print("[PASS] Scenario 13: Empty file upload (0 bytes) rejected gracefully with HTTP 400.")

    # Scenario 14: Malformed/corrupted PDF bytes -> HTTP 422
    r_bad_pdf = client.post("/upload", files={"file": ("corrupt.pdf", b"%PDF-invalid-bytes-non-parseable", "application/pdf")})
    assert r_bad_pdf.status_code == 422, f"Expected 422 for corrupt PDF, got {r_bad_pdf.status_code}"
    print("[PASS] Scenario 14: Malformed/corrupted PDF upload rejected gracefully with HTTP 422.")

    # Scenario 15: Blank text file -> HTTP 422
    r_blank = client.post("/upload", files={"file": ("blank.txt", b"   \n\n\t  ", "text/plain")})
    assert r_blank.status_code == 422, f"Expected 422 for blank text, got {r_blank.status_code}"
    print("[PASS] Scenario 15: Blank text file rejected gracefully with HTTP 422.")

    # Scenario 16: Unsupported file type -> HTTP 415
    r_unsupp = client.post("/upload", files={"file": ("scan.png", b"fake-png-data", "image/png")})
    assert r_unsupp.status_code == 415, f"Expected 415 for unsupported file type, got {r_unsupp.status_code}"
    print("[PASS] Scenario 16: Unsupported file type (.png) rejected with HTTP 415.")

    # Scenario 17: Actual source text preserved throughout upload workflow
    sample_txt_content = "DISCHARGE SUMMARY\nMEDICATIONS\n- Lisinopril 10 mg: take 1 tablet daily."
    r_txt_upload = client.post("/upload", files={"file": ("sample.txt", sample_txt_content.encode("utf-8"), "text/plain")})
    assert r_txt_upload.status_code == 200
    assert r_txt_upload.json()["source_text"] == sample_txt_content
    # Now verify /audit-output with this preserved source text
    r_audit = client.post(
        "/audit-output",
        json={
            "source_text": r_txt_upload.json()["source_text"],
            "candidate_medications": [{"name": "Oxycodone", "strength": "5 mg", "dose": "1 tablet"}],
        },
    )
    assert r_audit.status_code == 200
    audit_flags_res = r_audit.json()
    assert len(audit_flags_res) > 0, "Audit failed to flag hallucinated medication"
    assert "Oxycodone" in audit_flags_res[0]["title"]
    print("[PASS] Scenario 17: Genuine source text preserved through upload and verified by /audit-output.")

    # Scenario 18: Missing API key / honest AI provider status
    r_health = client.post("/analyze", json={"text": "Patient summary"})
    assert r_health.status_code == 200
    res_data = r_health.json()
    engine_mode = res_data["mode"]
    if not ai_adapter.is_llm_available:
        assert engine_mode == "deterministic-evidence-parser"
        assert "Deterministic Rules Engine" in ai_adapter.provider_name
        assert res_data.get("ai_patient_overview") is None
        print("[PASS] Scenario 18: Unconfigured API key honestly labeled as Deterministic Rules Engine (Zero-Inference).")
    else:
        assert engine_mode == "llm-assisted-parser"
        print(f"[PASS] Scenario 18: Live AI Provider active: {ai_adapter.provider_name}.")

    print("=====================================================================")
    print(" ALL 18 TEST SCENARIOS PASSED WITH 100% SUCCESS!")
    print("=====================================================================")
    return True


if __name__ == "__main__":
    run_tests()
