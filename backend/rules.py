"""Deterministic Extraction and Safety Audit Engine for Going Home Right.

Follows strict healthcare safety engineering principles:
1. Never invent missing medication instructions, appointments, or warning signs.
2. Retain exact source lines for all extracted fields.
3. Flag missing critical fields (dose, frequency, route, duration).
4. Detect ISMP 'Do Not Use' error-prone abbreviations.
5. Detect conflicting instructions within the same document without guessing.
6. Verify candidate outputs against source text to flag unsupported additions.
7. Separate medications into morning/afternoon/night ONLY when explicitly documented.
8. Correctly distinguish follow-up appointments from preparation instructions (never flag prep instructions as missing timing).
9. Provide natural bilingual conversational summaries (English and Hindi) for patient-friendly accessibility.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from models import (
    CareInstructionItem,
    DischargeAnalysisResponse,
    FollowUpItem,
    MedicationItem,
    SafetyFlag,
    ScheduleGroup,
    UnderstandingQuestion,
    WarningSignItem,
)

SECTION_HEADINGS = {
    "medication": ("medications", "medication", "medicines", "prescriptions", "discharge medications", "meds"),
    "followup": ("follow-up", "follow up", "appointments", "subsequent care", "clinic visits", "next steps"),
    "warning": ("warning signs", "when to call", "red flags", "emergencies", "seek help", "urgent symptoms"),
    "care": ("care instructions", "diet", "activity", "lifestyle", "wound care", "home care", "instructions", "general instructions"),
}

ISMP_ABBREVIATIONS = [
    (
        r"\b(?:MS|MSO4)\b",
        "Ambiguous abbreviation 'MS' detected",
        "The Institute for Safe Medication Practices (ISMP) designates 'MS' as high-risk because it can mean Morphine Sulfate or Magnesium Sulfate. Clinical verification required.",
    ),
    (
        r"\b(?:QD|Q\.D\.|qd)\b",
        "Ambiguous abbreviation 'QD' detected",
        "ISMP 'Do Not Use' list: 'QD' (once daily) is easily confused with QID (four times daily) or QOD (every other day). Clinical verification required.",
    ),
    (
        r"\b(?:QOD|Q\.O\.D\.|qod)\b",
        "Ambiguous abbreviation 'QOD' detected",
        "ISMP 'Do Not Use' list: 'QOD' (every other day) is easily mistaken for QD (daily). Clinical verification required.",
    ),
    (
        r"\b\d+\s*U\b",
        "Ambiguous abbreviation 'U' (Units) detected",
        "ISMP warns the abbreviation 'U' can be mistaken for the number '0' (zero), leading to a 10-fold overdose. Spell out 'units'.",
    ),
]

SHORT_COURSE_DRUGS = ("amoxicillin", "cephalexin", "azithromycin", "ciprofloxacin", "prednisone", "doxycycline", "augmentin")


def translate_frequency_hi(freq: str | None, slot: str | None) -> str:
    if not freq:
        return "Jaankari likhi nahi hai"
    f = freq.lower()
    if "once daily in the morning" in f or ("once daily" in f and slot == "morning"):
        return "Roz subah ek baar lein"
    if "once daily at bedtime" in f or ("once daily" in f and slot == "night"):
        return "Roz raat ko sote samay ek baar lein"
    if "twice daily with meals" in f or ("twice daily" in f and "meal" in f):
        return "Roz do baar khane ke sath lein"
    if "twice daily" in f:
        return "Roz do baar lein"
    if "3 times daily" in f:
        return "Din mein 3 baar lein"
    if "4 times daily" in f:
        return "Din mein 4 baar lein"
    if "every 6 hours as needed" in f:
        return "Har 6 ghante mein zaroorat padne par lein"
    if "every 4 to 6 hours as needed" in f:
        return "Har 4 se 6 ghante mein zaroorat padne par lein"
    if "as needed" in f or "prn" in f:
        return "Zaroorat padne par lein"
    if "once daily" in f:
        return "Roz ek baar lein"
    return f"{freq} ke anusaar lein"


def translate_dose_hi(dose: str | None) -> str:
    if not dose:
        return "Kitni leni hai likha nahi hai"
    d = dose.lower()
    d = re.sub(r"(\d+)\s*tablets?", r"\1 tablet (goli)", d)
    d = re.sub(r"(\d+)\s*capsules?", r"\1 capsule", d)
    d = re.sub(r"(\d+)\s*puffs?", r"\1 puff", d)
    d = re.sub(r"(\d+)\s*drops?", r"\1 boond (drop)", d)
    return d


def parse_raw_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADINGS}
    unlabeled: list[str] = []
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized_heading = re.sub(r"[^a-z -]", "", line.lower()).strip(" -:")
        matched_key = next((k for k, aliases in SECTION_HEADINGS.items() if normalized_heading in aliases), None)

        if matched_key:
            current_section = matched_key
            continue

        # Look for custom uppercase section headers
        if re.fullmatch(r"[A-Z][A-Z /&-]{2,}:?", line):
            current_section = None
            continue

        if current_section:
            sections[current_section].append(line)
        elif line.startswith(("-", "•", "*", "1.", "2.", "3.", "4.", "5.")):
            unlabeled.append(line)

    return sections, unlabeled


def extract_medication(line: str) -> tuple[MedicationItem, list[SafetyFlag]]:
    flags: list[SafetyFlag] = []
    reasons: list[str] = []
    clean_line = re.sub(r"^[-•*0-9.]\s*", "", line).strip()

    # Extract Name: first token or sequence before colon / dose
    name_match = re.match(r"^([A-Za-z][A-Za-z0-9\-/\s]+?)(?::|\s+\d|\s+take|\s+place|\s+inhale|\s+apply)", clean_line, re.I)
    med_name = name_match.group(1).strip() if name_match else clean_line.split()[0] if clean_line else "Unknown Medication"

    # Strength extraction: e.g., 500 mg, 10 mcg, 25 mg, 0.4 mg
    strength_match = re.search(r"\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|%))\b", clean_line, re.I)
    strength = strength_match.group(1) if strength_match else None

    # Dose extraction: e.g., 1 tablet, 2 capsules, 2 puffs, 1 drop
    dose_match = re.search(r"\b(\d+(?:\.\d+)?\s*(?:tablets?|capsules?|puffs?|drops?|pills?|patches?|units?))\b", clean_line, re.I)
    dose = dose_match.group(1) if dose_match else None

    # Route extraction: e.g., by mouth, oral, subcutaneous, under the tongue, topical, inhaled
    route_match = re.search(r"\b(by mouth|oral(?:ly)?|subcutaneous(?:ly)?|sublingually?|under the tongue|topical(?:ly)?|inhaled?|intravenous(?:ly)?|po)\b", clean_line, re.I)
    route = route_match.group(1) if route_match else None

    # Frequency extraction: e.g., once daily, twice daily, 3 times daily, every 6 hours
    freq_match = re.search(r"\b(once daily|twice daily|3 times daily|4 times daily|every \d+(?:\s*to\s*\d+)?\s*hours|each day|every morning|at bedtime|daily|as needed|prn)\b", clean_line, re.I)
    frequency = freq_match.group(1) if freq_match else None

    # Duration extraction: e.g., for 5 days, for 7 days, for 2 weeks
    dur_match = re.search(r"\b(for \d+(?:\s*to\s*\d+)?\s*(?:days|weeks|months)|until finished)\b", clean_line, re.I)
    duration = dur_match.group(1) if dur_match else None

    # Timing slot extraction: STRICT - only if explicitly mentioned
    timing_slot: Literal["morning", "afternoon", "night", "as_needed", "unspecified"] = "unspecified"
    lower_line = clean_line.lower()
    if "as needed" in lower_line or "prn" in lower_line:
        timing_slot = "as_needed"
    elif "in the morning" in lower_line or "every morning" in lower_line or "before breakfast" in lower_line or "with breakfast" in lower_line:
        timing_slot = "morning"
    elif "afternoon" in lower_line or "with lunch" in lower_line:
        timing_slot = "afternoon"
    elif "at bedtime" in lower_line or "at night" in lower_line or "in the evening" in lower_line:
        timing_slot = "night"

    # Safety checks
    if not strength:
        reasons.append("Missing medication strength (e.g., mg or mcg); confirm exact amount with a clinician.")
        flags.append(SafetyFlag(
            flag_id=f"missing-dose-{med_name}",
            category="missing_critical_field",
            severity="critical",
            title=f"Missing Dose for {med_name}",
            message=f"No strength or milligram dose specified in documented instruction: '{line}'.",
            source_passage=line,
            action_required="Do not guess strength. Confirm exact milligram/microgram dose with prescribing doctor or pharmacist."
        ))
    elif not dose:
        reasons.append("Missing dosage unit count (e.g., 1 tablet); confirm exact amount with a clinician.")

    if not frequency:
        reasons.append("Missing frequency or administration interval; confirm how often to take with a clinician.")
        flags.append(SafetyFlag(
            flag_id=f"missing-freq-{med_name}",
            category="missing_critical_field",
            severity="critical",
            title=f"Missing Frequency for {med_name}",
            message=f"Instruction does not state how many times daily to take '{med_name}': '{line}'.",
            source_passage=line,
            action_required="Contact clinic or pharmacy to verify daily schedule."
        ))

    # Short course medications (antibiotics/steroids) missing duration
    if any(drug in med_name.lower() for drug in SHORT_COURSE_DRUGS) and not duration and "as needed" not in lower_line:
        reasons.append(f"{med_name} is typically a limited course, but no duration was documented.")
        flags.append(SafetyFlag(
            flag_id=f"missing-dur-{med_name}",
            category="missing_critical_field",
            severity="warning",
            title=f"Missing Duration for {med_name}",
            message=f"Documented antibiotic or steroid course has no duration or end date: '{line}'.",
            source_passage=line,
            action_required="Confirm intended course length with prescriber to avoid premature stop or prolonged use."
        ))

    # ISMP Ambiguous abbreviations
    for pattern, title, message in ISMP_ABBREVIATIONS:
        if re.search(pattern, line):
            reasons.append(title)
            flags.append(SafetyFlag(
                flag_id=f"ismp-{med_name}-{title[:10]}",
                category="ambiguous_abbreviation",
                severity="critical" if "MS" in title or "U" in title else "warning",
                title=title,
                message=message,
                source_passage=line,
                action_required="Ask prescribing care team to clarify without abbreviations."
            ))

    # Vague instructions like "take as directed" without details
    if "as directed" in lower_line and not (strength and frequency):
        reasons.append("'Take as directed' is ambiguous without explicit bottle instructions.")
        flags.append(SafetyFlag(
            flag_id=f"vague-{med_name}",
            category="ambiguous_abbreviation",
            severity="warning",
            title=f"Ambiguous Instruction for {med_name}",
            message=f"Instruction states 'take as directed' without explicit schedule: '{line}'.",
            source_passage=line,
            action_required="Verify specific administration directions with care team."
        ))

    item_status: Literal["documented", "review", "unsupported"] = "review" if reasons else "documented"

    # Patient-friendly summaries
    summary_parts_en = [f"Take {med_name}"]
    if strength:
        summary_parts_en.append(strength)
    if dose:
        summary_parts_en.append(f"({dose})")
    if frequency:
        summary_parts_en.append(frequency)
    if timing_slot != "unspecified" and timing_slot != "as_needed":
        summary_parts_en.append(f"in the {timing_slot}")
    if duration:
        summary_parts_en.append(duration)
    patient_summary_en = " ".join(summary_parts_en) + "."

    dose_hi = translate_dose_hi(dose)
    freq_hi = translate_frequency_hi(frequency, timing_slot)
    patient_summary_hi = f"{med_name} {strength or ''}: {dose_hi}, {freq_hi}."

    safety_alert_en = None
    safety_alert_hi = None
    if item_status == "review":
        safety_alert_en = "Some important information about this medicine is missing. Please confirm with your doctor or pharmacist before acting on the unclear instruction."
        safety_alert_hi = "Is dawai ki kuch zaroori jaankari likhi nahi hai. Kripya dawai lene se pehle doctor ya pharmacist se confirm karein."

    med_item = MedicationItem(
        name=med_name,
        strength=strength,
        dose=dose,
        route=route,
        frequency=frequency,
        timing_slot=timing_slot,
        duration=duration,
        raw_text=clean_line,
        source_passage=line,
        status=item_status,
        review_reasons=reasons,
        patient_summary_en=patient_summary_en,
        patient_summary_hi=patient_summary_hi,
        safety_alert_en=safety_alert_en,
        safety_alert_hi=safety_alert_hi,
    )

    return med_item, flags


def parse_followup_section(lines: list[str]) -> tuple[list[FollowUpItem], list[SafetyFlag]]:
    """Parse follow-up lines cleanly distinguishing appointments, prep instructions, and phone contacts.

    CRITICAL RULE: Never classify preparation instructions (e.g. 'Bring medication bottles') as missing appointment timing!
    """
    items: list[FollowUpItem] = []
    flags: list[SafetyFlag] = []

    # Separate appointment statements from standalone prep/contact lines
    appointment_lines: list[str] = []
    prep_instructions: list[str] = []
    shared_phone: str | None = None

    prep_pattern = re.compile(r"^(?:bring|fast|arrive|do not eat|wear|check in|record|weigh|bring all)\b|transportation|blood pressure log", re.I)
    phone_pattern = re.compile(r"(\(?\d{3}\)?[\s.-]?(?:\d{3}[\s.-]?)?\d{4})")

    for raw in lines:
        clean = re.sub(r"^[-•*0-9.]\s*", "", raw).strip()
        if not clean:
            continue

        # Check for phone
        m_phone = phone_pattern.search(clean)
        if m_phone:
            shared_phone = m_phone.group(1)

        # Check if this line is purely a preparation instruction
        if prep_pattern.search(clean) and not re.search(r"\b(?:appointment|dr\.|doctor|clinic in|return to)\b", clean, re.I):
            prep_instructions.append(clean)
        elif clean.lower().startswith("call ") and not re.search(r"\b(?:appointment in|follow-up in)\b", clean, re.I):
            # A call/reschedule instruction line
            pass
        else:
            appointment_lines.append(raw)

    # If there are appointment lines, process them
    if appointment_lines:
        for line in appointment_lines:
            clean = re.sub(r"^[-•*0-9.]\s*", "", line).strip()
            timing_match = re.search(
                r"\b(in \d+ (?:days|weeks|months)|on [A-Z][a-z]+ \d{1,2}(?:, \d{4})?(?: at \d{1,2}:\d{2}\s*(?:AM|PM)?)?)\b",
                clean,
                re.I,
            )
            timing = timing_match.group(1) if timing_match else None

            phone_match = phone_pattern.search(clean)
            contact = phone_match.group(1) if phone_match else shared_phone

            provider = clean.split(".")[0].strip()

            reasons: list[str] = []
            timing_missing = False
            timing_alert_en = None
            timing_alert_hi = None

            if not timing:
                timing_missing = True
                reasons.append("Follow-up appointment does not provide specific timing or date.")
                timing_alert_en = "The appointment date or time is not documented. Please contact the clinic to confirm."
                timing_alert_hi = "Mulaqat ki tareekh ya samay nahi likha hai. Kripya clinic se poochhein."
                flags.append(SafetyFlag(
                    flag_id=f"missing-followup-timing-{clean[:15]}",
                    category="missing_timing",
                    severity="warning",
                    title="Missing Follow-Up Timing",
                    message=f"Documented follow-up does not specify appointment date or timeframe: '{line}'.",
                    source_passage=line,
                    action_required="Contact clinic to confirm when appointment should take place."
                ))

            # Patient-friendly summaries
            if timing:
                patient_summary_en = f"Your appointment is on {timing}. Provider: {provider}."
                patient_summary_hi = f"Aapki doctor se mulaqat {timing} ko hai ({provider})."
            else:
                patient_summary_en = "Follow-up is recommended, but the date or time is not written in your paperwork."
                patient_summary_hi = "Doctor se milna hai, lekin tareekh ya samay kagaz par nahi likha hai."

            item = FollowUpItem(
                provider_or_clinic=provider,
                timing=timing,
                contact=contact,
                actions=[clean],
                prep_instructions=prep_instructions,
                raw_text=clean,
                source_passage=line,
                status="review" if reasons else "documented",
                review_reasons=reasons,
                patient_summary_en=patient_summary_en,
                patient_summary_hi=patient_summary_hi,
                timing_missing=timing_missing,
                timing_alert_en=timing_alert_en,
                timing_alert_hi=timing_alert_hi,
            )
            items.append(item)
    elif prep_instructions:
        # Only prep instructions found under follow-up
        item = FollowUpItem(
            provider_or_clinic="Clinic Preparation",
            timing=None,
            contact=shared_phone,
            actions=prep_instructions,
            prep_instructions=prep_instructions,
            raw_text="; ".join(prep_instructions),
            source_passage="; ".join(prep_instructions),
            status="documented",
            review_reasons=[],
            patient_summary_en="Preparation instructions: " + "; ".join(prep_instructions),
            patient_summary_hi="Taiyari ke nirdesh: " + "; ".join(prep_instructions),
            timing_missing=False,
        )
        items.append(item)

    return items, flags


def extract_warning(line: str) -> WarningSignItem:
    clean_line = re.sub(r"^[-•*0-9.]\s*", "", line).strip()
    lower = clean_line.lower()

    # Distinguish emergency only if document explicitly specifies emergency, 911, urgent care, or immediately
    is_emergency = any(kw in lower for kw in ("emergency", "911", "urgent care", "immediately", "urgent emergency", "seek urgent"))
    severity: Literal["urgent_emergency", "care_team_call"] = "urgent_emergency" if is_emergency else "care_team_call"
    action = "Seek immediate emergency medical care / call 911" if is_emergency else "Call care team clinic within 24 hours"

    if is_emergency:
        patient_summary_en = f"EMERGENCY: Seek immediate medical care or call 911 for: {clean_line}."
        patient_summary_hi = f"Khatre ki ghanti (Emergency): Aise lakshan dikhein to turant 911 ya hospital jayein: {clean_line}."
    else:
        patient_summary_en = f"Care team notification: Call your clinic if you experience: {clean_line}."
        patient_summary_hi = f"Clinic ko phone karein: Agar aisa lage to clinic se baat karein: {clean_line}."

    return WarningSignItem(
        sign=clean_line,
        action=action,
        severity=severity,
        raw_text=clean_line,
        source_passage=line,
        patient_summary_en=patient_summary_en,
        patient_summary_hi=patient_summary_hi,
    )


def extract_care_instruction(line: str) -> CareInstructionItem:
    clean_line = re.sub(r"^[-•*0-9.]\s*", "", line).strip()
    lower = clean_line.lower()

    if any(k in lower for k in ("wound", "dressing", "incision", "bandage")):
        category = "Wound Care"
        hi_cat = "Ghaav ki dekhbhaal"
    elif any(k in lower for k in ("diet", "water", "sodium", "eat", "drink", "food")):
        category = "Diet & Nutrition"
        hi_cat = "Khana peena (Diet)"
    elif any(k in lower for k in ("lift", "walk", "exercise", "rest", "activity")):
        category = "Physical Activity"
        hi_cat = "Chalna firna aur aaraam"
    else:
        category = "General Home Care"
        hi_cat = "Ghar par aam dekhbhaal"

    return CareInstructionItem(
        category=category,
        instruction=clean_line,
        raw_text=clean_line,
        source_passage=line,
        status="documented",
        review_reasons=[],
        patient_summary_en=f"{category}: {clean_line}",
        patient_summary_hi=f"{hi_cat}: {clean_line}",
    )


def check_conflicts(medications: list[MedicationItem]) -> list[SafetyFlag]:
    flags: list[SafetyFlag] = []
    grouped: dict[str, list[MedicationItem]] = {}

    for med in medications:
        normalized_name = re.sub(r"[^a-z]", "", med.name.lower())
        if normalized_name:
            grouped.setdefault(normalized_name, []).append(med)

    for norm_name, items in grouped.items():
        if len(items) > 1:
            # Check if instructions differ
            unique_texts = {item.raw_text.casefold() for item in items}
            if len(unique_texts) > 1:
                display_name = items[0].name
                passages = " VS ".join([f"'{it.source_passage}'" for it in items])
                for it in items:
                    it.status = "review"
                    it.review_reasons.append("Conflicting instructions found in document; requires clinical clarification.")
                    it.safety_alert_en = f"Conflicting instructions detected for {display_name}. Please confirm the correct directions with your doctor before taking."
                    it.safety_alert_hi = f"{display_name} ke liye alag-alag nirdesh likhe hain. Sahi tareeka doctor se confirm karein."

                flags.append(SafetyFlag(
                    flag_id=f"conflict-{norm_name}",
                    category="conflicting_instructions",
                    severity="critical",
                    title=f"Conflicting Instructions for {display_name}",
                    message=f"Document contains contradictory directions for {display_name}: {passages}.",
                    source_passage=passages,
                    action_required="Do not attempt to guess which instruction is correct. Contact prescribing physician immediately."
                ))

    return flags


def generate_teach_back_questions(
    medications: list[MedicationItem],
    follow_ups: list[FollowUpItem],
    warning_signs: list[WarningSignItem],
    safety_flags: list[SafetyFlag],
) -> list[UnderstandingQuestion]:
    questions: list[UnderstandingQuestion] = []
    q_idx = 1

    # Q1: Follow-up timing
    if follow_ups:
        fu = follow_ups[0]
        if fu.timing:
            questions.append(UnderstandingQuestion(
                id=f"tb-{q_idx}",
                question="When is your follow-up appointment according to the discharge paperwork?",
                question_hi="Kagaz ke anusaar, aapki doctor se agli mulaqat kab hai?",
                options=[fu.timing, "Tomorrow morning", "No follow-up was recommended", "I don't understand"],
                options_hi=[fu.timing, "Kal subah", "Doctor ne milne ko nahi kaha", "Mujhe samajh nahi aaya"],
                correct_index=0,
                explanation=f"The paperwork explicitly states: '{fu.source_passage}'. Always keep this scheduled visit.",
                explanation_hi=f"Kagaz mein saaf likha hai: '{fu.source_passage}'. Is din clinic zaroor jayein.",
                source_passage=fu.source_passage,
                is_ambiguous=False,
            ))
        else:
            questions.append(UnderstandingQuestion(
                id=f"tb-{q_idx}",
                question="What does the discharge paperwork say about your follow-up appointment timing?",
                question_hi="Aapki doctor se mulaqat ke samay ke baare mein kagaz kya kehta hai?",
                options=[
                    "A specific date is scheduled",
                    "Timing is missing; you need to call the clinic to confirm",
                    "No follow-up is needed",
                    "I don't understand",
                ],
                options_hi=[
                    "Khas tareekh tay hai",
                    "Tareekh nahi likhi hai; clinic se poochkar pakka karein",
                    "Milne ki zaroorat nahi hai",
                    "Mujhe samajh nahi aaya",
                ],
                correct_index=1,
                explanation="The document mentions a follow-up but lacks an exact date or timeframe, so human verification is required.",
                explanation_hi="Kagaz mein doctor se milne ka zikr hai par tareekh nahi hai, isliye clinic se confirm karna zaroori hai.",
                source_passage=fu.source_passage,
                is_ambiguous=True,
                verification_note="Timing is missing in document; contact clinic.",
            ))
        q_idx += 1

    # Q2: Medication frequency/timing
    documented_meds = [m for m in medications if m.frequency and m.status == "documented"]
    if documented_meds:
        med = documented_meds[0]
        freq_hi = translate_frequency_hi(med.frequency, med.timing_slot)
        questions.append(UnderstandingQuestion(
            id=f"tb-{q_idx}",
            question=f"According to your instructions, how often should you take {med.name}?",
            question_hi=f"Kagaz ke anusaar, {med.name} kitni baar leni hai?",
            options=[
                f"{med.frequency}" + (f" ({med.timing_slot})" if med.timing_slot != "unspecified" else ""),
                "Take double dose if you feel more pain",
                "Stop taking it as soon as symptoms slightly improve",
                "I don't understand",
            ],
            options_hi=[
                freq_hi,
                "Dard badhne par do guna dawai lein",
                "Thoda aaraam milte hi dawai band kar dein",
                "Mujhe samajh nahi aaya",
            ],
            correct_index=0,
            explanation=f"Documented instruction states: '{med.source_passage}'. Never alter frequency without clinical advice.",
            explanation_hi=f"Kagaz par likha hai: '{med.source_passage}'. Doctor ki salah ke bina dawai ka niyam na badlein.",
            source_passage=med.source_passage,
            is_ambiguous=False,
        ))
        q_idx += 1

    # Q3: Warning sign response
    emergency_warnings = [w for w in warning_signs if w.severity == "urgent_emergency"]
    if emergency_warnings:
        warn = emergency_warnings[0]
        questions.append(UnderstandingQuestion(
            id=f"tb-{q_idx}",
            question="What should you do if you experience severe symptoms like chest pain or difficulty breathing?",
            question_hi="Agar chhaati mein tez dard ya saans lene mein takleef ho, to kya karna chahiye?",
            options=[
                "Wait until your follow-up appointment next week",
                "Seek immediate emergency medical care / call 911",
                "Take an extra dose of pain medicine and rest",
                "I don't understand",
            ],
            options_hi=[
                "Agle hafte doctor ki mulaqat tak intezar karein",
                "Turant hospital / emergency jayein ya 911 par call karein",
                "Dard ki goli lekar so jayein",
                "Mujhe samajh nahi aaya",
            ],
            correct_index=1,
            explanation=f"Emergency warning signs require prompt emergency evaluation: '{warn.source_passage}'.",
            explanation_hi=f"Aise gambhir lakshano mein bina deri kiye emergency hospital jana zaroori hai: '{warn.source_passage}'.",
            source_passage=warn.source_passage,
            is_ambiguous=False,
        ))
        q_idx += 1

    # Q4: Handling unclear or missing information
    questions.append(UnderstandingQuestion(
        id=f"tb-{q_idx}",
        question="What should you do if any discharge instruction is missing, unclear, or conflicting?",
        question_hi="Agar koi dawai ya nirdesh samajh na aaye ya adhoora lage, to kya karein?",
        options=[
            "Search online and guess what usual care might be",
            "Contact your hospital discharge team or primary care physician to verify",
            "Skip that instruction entirely",
            "I don't understand",
        ],
        options_hi=[
            "Internet par dekh kar khud andaza lagayein",
            "Apne doctor, hospital ya pharmacist se poochkar pakka karein",
            "Dawai ko chhod dein",
            "Mujhe samajh nahi aaya",
        ],
        correct_index=1,
        explanation="Safety rule: AI companions and patients should never invent or guess missing care details. Always confirm with the clinical team.",
        explanation_hi="Suraksha niyam: Andaza mat lagaiye. Hamesha doctor ya hospital ki team se poochkar pakka karein.",
        source_passage="Safety Protocol: Never guess clinical details.",
        is_ambiguous=False,
    ))
    q_idx += 1

    return questions


def analyze_discharge_text(text: str, test_case_id: str | None = None) -> DischargeAnalysisResponse:
    sections, unlabeled = parse_raw_sections(text)

    all_medications: list[MedicationItem] = []
    all_safety_flags: list[SafetyFlag] = []
    all_warnings: list[WarningSignItem] = []
    all_care: list[CareInstructionItem] = []

    # 1. Medications
    for line in sections["medication"]:
        item, flags = extract_medication(line)
        all_medications.append(item)
        all_safety_flags.extend(flags)

    # 2. Check conflicts among medications
    conflict_flags = check_conflicts(all_medications)
    all_safety_flags.extend(conflict_flags)

    # 3. Follow-up (using refined parser that protects preparation instructions)
    all_followups, fu_flags = parse_followup_section(sections["followup"])
    all_safety_flags.extend(fu_flags)

    # 4. Warnings
    for line in sections["warning"]:
        item = extract_warning(line)
        all_warnings.append(item)

    # 5. Care instructions
    for line in sections["care"]:
        item = extract_care_instruction(line)
        all_care.append(item)

    # 6. Check missing entire sections
    if not sections["medication"]:
        all_safety_flags.append(SafetyFlag(
            flag_id="missing-section-medications",
            category="missing_critical_field",
            severity="warning",
            title="No Documented Medications Found",
            message="No medication section was detected under recognized headings. Human review required.",
            action_required="Confirm with doctor whether patient has active discharge prescriptions."
        ))

    if not sections["followup"]:
        all_safety_flags.append(SafetyFlag(
            flag_id="missing-section-followup",
            category="missing_timing",
            severity="warning",
            title="No Documented Follow-up Found",
            message="No follow-up plan found under recognized headings. Human review required.",
            action_required="Confirm post-discharge follow-up provider and timeline."
        ))

    if not sections["warning"]:
        all_safety_flags.append(SafetyFlag(
            flag_id="missing-section-warning",
            category="general_review",
            severity="warning",
            title="No Warning Signs Found",
            message="No red flag / warning symptoms were documented under recognized headings.",
            action_required="Ask care team what symptoms require urgent evaluation."
        ))

    if unlabeled:
        all_safety_flags.append(SafetyFlag(
            flag_id="unlabeled-bullet-points",
            category="general_review",
            severity="info",
            title="Uncategorized Notes Detected",
            message=f"{len(unlabeled)} lines were not under recognized headings and were preserved without categorization.",
            source_passage="\n".join(unlabeled[:3]),
            action_required="Review uncategorized text manually."
        ))

    # 7. Organize schedule group
    schedule = ScheduleGroup()
    for med in all_medications:
        if med.timing_slot == "morning":
            schedule.morning.append(med)
        elif med.timing_slot == "afternoon":
            schedule.afternoon.append(med)
        elif med.timing_slot == "night":
            schedule.night.append(med)
        elif med.timing_slot == "as_needed":
            schedule.as_needed.append(med)
        else:
            schedule.documented_frequency.append(med)

    # 8. Teach-back questions
    teach_back = generate_teach_back_questions(
        all_medications, all_followups, all_warnings, all_safety_flags
    )

    summary = {
        "medications": len(all_medications),
        "followUps": len(all_followups),
        "warningSigns": len(all_warnings),
        "careInstructions": len(all_care),
        "criticalSafetyFlags": sum(1 for f in all_safety_flags if f.severity == "critical"),
        "warningFlags": sum(1 for f in all_safety_flags if f.severity == "warning"),
        "needsReviewCount": sum(1 for m in all_medications if m.status == "review") + len(all_safety_flags),
    }

    return DischargeAnalysisResponse(
        mode="deterministic-evidence-parser",
        document_title="Synthetic Discharge Summary",
        medications=all_medications,
        follow_ups=all_followups,
        warning_signs=all_warnings,
        care_instructions=all_care,
        schedule=schedule,
        safety_flags=all_safety_flags,
        teach_back=teach_back,
        summary=summary,
    )


def audit_candidate_medications(source_text: str, candidate_meds: list[dict[str, Any]]) -> list[SafetyFlag]:
    """Safety Audit to catch unsupported medication additions or candidate discrepancies."""
    flags: list[SafetyFlag] = []
    source_lower = source_text.lower()

    for item in candidate_meds:
        name = item.get("name", "").strip()
        if not name:
            continue

        normalized_name = re.escape(name.lower())
        found = bool(re.search(rf"\b{normalized_name}\b", source_lower))

        if not found:
            flags.append(SafetyFlag(
                flag_id=f"unsupported-{name}",
                category="unsupported_addition",
                severity="critical",
                title=f"CRITICAL: Unsupported Medication '{name}'",
                message=(
                    f"Candidate output includes medication '{name}', but this drug is NOT mentioned "
                    "anywhere in the source discharge document! Potential hallucination or unsupported addition."
                ),
                source_passage="Not found in source document",
                action_required="CRITICAL SAFETY VIOLATION: Exclude this medication immediately and flag for clinician audit."
            ))

    return flags
