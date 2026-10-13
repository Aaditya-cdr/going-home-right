# AAYU 2026 — Going Home Right

**Problem Statement T03 — Going Home Right: Evidence-Linked Discharge Care Companion**  
*Patient-Friendly · Bilingual (Hindi & English) · Voice-First · Evidence-Linked*

A healthcare safety-first hackathon prototype that turns **synthetic discharge summaries** into simple, accessible care plans for patients, elderly users, and caregivers, while maintaining strict evidence traceability and deterministic clinical validation for healthcare professionals and reviewers.

---

## 🌟 Key Features & Two Distinct Experiences

### A. Patient & Caregiver Mode (Default Landing Experience)
- **Accessible, Mobile-First UI:** Large touch targets (≥ 48px), calm colors, high contrast, readable typography, and zero technical jargon.
- **Bilingual Support (हिंदी & English):** Instant language toggle updating all text, safety notices, and voice explanations simultaneously into natural, conversational language.
- **Voice-First Audio (🔊 Listen / सुनकर समझें):** Reads verified explanations aloud using the browser's Web Speech API (`hi-IN` for Hindi, `en-IN` / `en-US` for English) with Play, Stop, and Replay controls.
- **Four Core Patient Actions:**
  1. 💊 **My Medicines / मेरी दवाइयां:** Single-card view per drug with strength, dose, timing, audio explanation, and safety alert if information is missing.
  2. 🩺 **Doctor Visit / डॉक्टर से मुलाक़ात:** Clear appointment timing, clinic phone, and preparation steps.
  3. 🏠 **Home Care / घर पर देखभाल:** Verified wound care, diet, and activity instructions.
  4. 🆘 **I Need Help / मुझे मदद चाहिए:** Urgent red-flag warning signs, routine clinic calls, and verified hospital phone numbers.
- **Supportive Teach-Back Check:** Step-by-step comprehension check with simple questions, option to say "I don't understand / मुझे समझ नहीं आया", and encouraging evidence-backed explanations.
- **"Where is this written? / यह कहाँ लिखा है?":** Direct expandable drawer revealing the original verbatim source sentence for any item.

### B. Technical & Reviewer Dashboard (Accessible via Header Toggle)
- **10 Synthetic Clinical Edge Cases:** Baseline complete, missing dose, missing frequency, missing duration, conflicting timings, documented appointment, warning signs, hallucination filter test, ISMP abbreviations, and multi-med strict time slots.
- **Deterministic Extraction & Safety Rules:** Strict time-slot partitioning (Morning, Afternoon, Bedtime, PRN) only when explicitly supported; no guessing.
- **Clinical Classification Fix:** Preparation instructions (e.g. "Bring medication bottles") are correctly categorized as prep steps and never misclassified as missing appointment timing.
- **Hallucination Defense:** Test button to simulate unsupported medication additions and demonstrate deterministic safety blocking.
- **PyMuPDF Document Upload:** Native text PDF and TXT processing with selectable text validation.

---

## 🚀 Run Locally

### Requirements
- Python 3.10+
- Node.js 20+

### 1. Start Backend API
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- API Root: http://localhost:8000/
- API Swagger Docs: http://localhost:8000/docs
- Test Cases Endpoint: http://localhost:8000/test-cases

### 2. Run Automated Synthetic Test Suite
```powershell
cd backend
.\.venv\Scripts\python.exe test_suite.py
```
*Asserts all 10 clinical test cases pass, including prep instruction classification.*

### 3. Start Frontend Web App
```powershell
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000** in your browser.

---

## 🧪 Synthetic Test Cases Suite

| Case ID | Title | Key Safety Check |
|---|---|---|
| `case-1-complete` | Complete Discharge Instructions | Clean baseline with all sections and 0 critical flags |
| `case-2-missing-dose` | Missing Medication Dose | Flags missing milligram strength for Lisinopril |
| `case-3-missing-frequency` | Missing Medication Frequency | Flags missing daily frequency for Amoxicillin |
| `case-4-missing-duration` | Missing Duration for Course | Flags missing duration for Prednisone taper/course |
| `case-5-conflicting-timings` | Conflicting Timings / Instructions | Flags contradictory Metformin instructions (twice daily vs bedtime) |
| `case-6-follow-up` | Documented Follow-up Appointment | Extracts appointment date, clinic phone, and prep instructions without false timing flags |
| `case-7-warning-signs` | Documented Warning Signs | Partitions emergency signs (911) from routine clinic calls |
| `case-8-unsupported-addition` | Unsupported Medication Addition | Safety audit catches hallucinated Oxycodone not in source |
| `case-9-ambiguous-abbreviation` | Ambiguous Abbreviations | Flags ISMP 'Do Not Use' error-prone abbreviations (`MS`, `QD`, `U`) |
| `case-10-multiple-meds` | Multiple Medications & Time Slots | Strictly assigns morning/lunch/bedtime without guessing |

---

## ⚠️ Prototype Clinical Disclaimer

This application is a synthetic-data hackathon prototype for demonstration and accessibility research. It does not provide medical diagnosis, treatment recommendations, or real-time clinical care decisions. If any discharge instruction is missing, unclear, or conflicting, patients must confirm directly with their healthcare team.
