"""Automated Test Suite for Going Home Right.

Tests all 10 synthetic edge cases and asserts expected clinical safety validation behavior.
"""

from dataset import get_test_cases
from rules import analyze_discharge_text, audit_candidate_medications


def run_tests() -> bool:
    print("=====================================================================")
    print(" RUNNING AAYU 2026 'GOING HOME RIGHT' SYNTHETIC DATASET TEST SUITE")
    print("=====================================================================")

    cases = {c["id"]: c for c in get_test_cases()}
    all_passed = True

    # Test 1: Complete baseline
    c1 = cases["case-1-complete"]
    res1 = analyze_discharge_text(c1["source_text"])
    critical1 = [f for f in res1.safety_flags if f.severity == "critical"]
    assert len(critical1) == 0, f"Case 1 had unexpected critical flags: {critical1}"
    assert len(res1.medications) >= 3, "Case 1 should extract 3 medications"
    assert len(res1.follow_ups) >= 1, "Case 1 should extract follow-up"
    assert len(res1.warning_signs) >= 2, "Case 1 should extract warning signs"
    print("[PASS] Case 1: Complete instructions baseline parsed cleanly with 0 critical flags.")

    # Test 2: Missing dose
    c2 = cases["case-2-missing-dose"]
    res2 = analyze_discharge_text(c2["source_text"])
    has_dose_flag = any("Missing Dose for Lisinopril" in f.title for f in res2.safety_flags)
    assert has_dose_flag, f"Case 2 failed to flag missing dose for Lisinopril. Flags: {[f.title for f in res2.safety_flags]}"
    print("[PASS] Case 2: Missing dose for Lisinopril correctly identified and flagged.")

    # Test 3: Missing frequency
    c3 = cases["case-3-missing-frequency"]
    res3 = analyze_discharge_text(c3["source_text"])
    has_freq_flag = any("Missing Frequency for Amoxicillin" in f.title for f in res3.safety_flags)
    assert has_freq_flag, f"Case 3 failed to flag missing frequency for Amoxicillin. Flags: {[f.title for f in res3.safety_flags]}"
    print("[PASS] Case 3: Missing frequency for Amoxicillin correctly identified and flagged.")

    # Test 4: Missing duration
    c4 = cases["case-4-missing-duration"]
    res4 = analyze_discharge_text(c4["source_text"])
    has_dur_flag = any("Missing Duration for Prednisone" in f.title for f in res4.safety_flags)
    assert has_dur_flag, f"Case 4 failed to flag missing duration for Prednisone. Flags: {[f.title for f in res4.safety_flags]}"
    print("[PASS] Case 4: Missing course duration for Prednisone correctly flagged.")

    # Test 5: Conflicting instructions
    c5 = cases["case-5-conflicting-timings"]
    res5 = analyze_discharge_text(c5["source_text"])
    has_conflict = any("Conflicting Instructions for Metformin" in f.title for f in res5.safety_flags)
    assert has_conflict, f"Case 5 failed to flag contradictory Metformin directions. Flags: {[f.title for f in res5.safety_flags]}"
    print("[PASS] Case 5: Contradictory Metformin instructions preserved and flagged for human review.")

    # Test 6: Documented follow-up appointment
    c6 = cases["case-6-follow-up"]
    res6 = analyze_discharge_text(c6["source_text"])
    has_timing = any(f.timing and "October 22, 2026" in f.timing for f in res6.follow_ups)
    has_contact = any(f.contact and "0123" in f.contact for f in res6.follow_ups)
    assert has_timing, f"Case 6 did not capture appointment timing in follow-ups: {[f.timing for f in res6.follow_ups]}"
    assert has_contact, f"Case 6 did not capture phone contact in follow-ups: {[f.contact for f in res6.follow_ups]}"
    # Verify prep instruction classification: preparation steps must NOT be classified as missing appointment timing!
    has_prep = any(any("bottles" in p.lower() for p in f.prep_instructions) for f in res6.follow_ups)
    assert has_prep, "Case 6 failed to associate preparation instructions ('Bring bottles...')"
    has_false_missing_timing = any(f.category == "missing_timing" for f in res6.safety_flags)
    assert not has_false_missing_timing, f"Case 6 generated false-positive missing timing flags: {[f.title for f in res6.safety_flags]}"
    print("[PASS] Case 6: Documented follow-up timing and clinic phone extracted accurately; prep instructions NOT flagged as missing timing.")

    # Test 7: Documented warning signs triage
    c7 = cases["case-7-warning-signs"]
    res7 = analyze_discharge_text(c7["source_text"])
    emergency_signs = [w for w in res7.warning_signs if w.severity == "urgent_emergency"]
    routine_signs = [w for w in res7.warning_signs if w.severity == "care_team_call"]
    assert len(emergency_signs) >= 1, "Case 7 should have emergency signs"
    assert len(routine_signs) >= 1, "Case 7 should have routine call signs"
    print("[PASS] Case 7: Warning signs accurately partitioned into emergency triage vs clinic calls.")

    # Test 8: Unsupported medication addition (safety audit)
    c8 = cases["case-8-unsupported-addition"]
    simulated = [c8["simulated_hallucination"]]
    audit_flags = audit_candidate_medications(c8["source_text"], simulated)
    assert len(audit_flags) > 0, "Case 8 should catch unsupported Oxycodone addition"
    assert "Oxycodone" in audit_flags[0].title, f"Case 8 flag mismatch: {audit_flags[0].title}"
    print("[PASS] Case 8: Safety audit caught unsupported medication addition (hallucination guard active).")

    # Test 9: Ambiguous abbreviations (ISMP Do Not Use list)
    c9 = cases["case-9-ambiguous-abbreviation"]
    res9 = analyze_discharge_text(c9["source_text"])
    flag_titles = [f.title for f in res9.safety_flags]
    has_ms = any("MS" in t for t in flag_titles)
    has_qd = any("QD" in t for t in flag_titles)
    has_u = any("Units" in t or "U" in t for t in flag_titles)
    assert has_ms and has_qd and has_u, f"Case 9 failed to flag all ISMP abbreviations. Flags: {flag_titles}"
    print("[PASS] Case 9: ISMP error-prone abbreviations ('MS', 'QD', 'U') detected and flagged.")

    # Test 10: Multiple medications schedule slots
    c10 = cases["case-10-multiple-meds"]
    res10 = analyze_discharge_text(c10["source_text"])
    assert len(res10.schedule.morning) >= 1, "Should have morning meds"
    assert len(res10.schedule.afternoon) >= 1, "Should have afternoon meds"
    assert len(res10.schedule.night) >= 1, "Should have night meds"
    assert len(res10.schedule.as_needed) >= 1, "Should have as_needed meds"
    assert res10.schedule.morning[0].name.startswith("Levothyroxine")
    assert res10.schedule.afternoon[0].name.startswith("Furosemide")
    assert res10.schedule.night[0].name.startswith("Atorvastatin")
    print("[PASS] Case 10: Multiple medications parsed into explicit documented time slots without guessing.")

    print("=====================================================================")
    print(" ALL 10 SYNTHETIC TEST CASES PASSED WITH 100% SUCCESS!")
    print("=====================================================================")
    return True


if __name__ == "__main__":
    run_tests()
