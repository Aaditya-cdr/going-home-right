"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";

type MedicationItem = {
  name: string;
  strength: string | null;
  dose: string | null;
  route: string | null;
  frequency: string | null;
  timing_slot: "morning" | "afternoon" | "night" | "as_needed" | "unspecified";
  duration: string | null;
  raw_text: string;
  source_passage: string;
  status: "documented" | "review" | "unsupported";
  review_reasons: string[];
  patient_summary_en?: string;
  patient_summary_hi?: string;
  safety_alert_en?: string | null;
  safety_alert_hi?: string | null;
};

type FollowUpItem = {
  provider_or_clinic: string;
  timing: string | null;
  contact: string | null;
  actions: string[];
  prep_instructions?: string[];
  raw_text: string;
  source_passage: string;
  status: "documented" | "review";
  review_reasons: string[];
  patient_summary_en?: string;
  patient_summary_hi?: string;
  timing_missing?: boolean;
  timing_alert_en?: string | null;
  timing_alert_hi?: string | null;
};

type WarningSignItem = {
  sign: string;
  action: string;
  severity: "urgent_emergency" | "care_team_call";
  raw_text: string;
  source_passage: string;
  patient_summary_en?: string;
  patient_summary_hi?: string;
};

type CareInstructionItem = {
  category: string;
  instruction: string;
  raw_text: string;
  source_passage: string;
  status: "documented" | "review";
  review_reasons: string[];
  patient_summary_en?: string;
  patient_summary_hi?: string;
};

type SafetyFlag = {
  flag_id: string;
  category: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  source_passage?: string | null;
  action_required: string;
};

type Question = {
  id: string;
  question: string;
  question_hi?: string;
  options: string[];
  options_hi?: string[];
  correct_index: number;
  explanation: string;
  explanation_hi?: string;
  source_passage: string;
  is_ambiguous?: boolean;
};

type ScheduleGroup = {
  morning: MedicationItem[];
  afternoon: MedicationItem[];
  night: MedicationItem[];
  as_needed: MedicationItem[];
  documented_frequency: MedicationItem[];
};

type AnalysisResult = {
  mode: string;
  document_title: string;
  medications: MedicationItem[];
  follow_ups: FollowUpItem[];
  warning_signs: WarningSignItem[];
  care_instructions: CareInstructionItem[];
  schedule: ScheduleGroup;
  safety_flags: SafetyFlag[];
  teach_back: Question[];
  summary: Record<string, number>;
  disclaimer: string;
};

type TestCase = {
  id: string;
  title: string;
  description: string;
  edge_case_type: string;
  source_text: string;
  expected_flags: string[];
  simulated_hallucination?: any;
};

const API = process.env.NEXT_PUBLIC_API_URL || "";

type PatientSection = "home" | "medicines" | "followup" | "homecare" | "help" | "teachback";

export default function Home() {
  // Mode: "patient" (default friendly view) vs "technical" (reviewer dashboard)
  const [viewMode, setViewMode] = useState<"patient" | "technical">("patient");
  // Language: "en" vs "hi"
  const [lang, setLang] = useState<"en" | "hi">("hi");
  // Active screen in Patient Mode
  const [patientSection, setPatientSection] = useState<PatientSection>("home");

  // Core Data
  const [text, setText] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");

  // Technical view filters
  const [activeSlot, setActiveSlot] = useState<string>("all");
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [auditMessage, setAuditMessage] = useState<string>("");

  // Teach-back quiz state
  const [currentQuizIdx, setCurrentQuizIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});

  // Audio Speech state
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [audioStatusText, setAudioStatusText] = useState("");
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Load test cases on mount
  useEffect(() => {
    fetchTestCases();
  }, []);

  // Stop speech whenever language, section, or viewMode changes
  useEffect(() => {
    stopAudio();
  }, [lang, patientSection, viewMode]);

  async function fetchTestCases() {
    try {
      const res = await fetch(`${API}/test-cases`);
      if (res.ok) {
        const data = await res.json();
        setTestCases(data);
        if (data.length > 0) {
          selectTestCase(data[0]);
        }
      }
    } catch {
      // Backend starting up or offline
    }
  }

  async function selectTestCase(tc: TestCase) {
    setSelectedCaseId(tc.id);
    setText(tc.source_text);
    setAnswers({});
    setExpandedSources({});
    setError("");
    setAuditMessage("");
    setCurrentQuizIdx(0);
    stopAudio();
    // Automatically analyze selected case for immediate patient/dashboard view
    analyzeTextDirectly(tc.source_text, tc.id);
  }

  async function analyzeTextDirectly(rawText: string, caseId?: string) {
    if (!rawText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`${API}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: rawText, test_case_id: caseId || null }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Analysis failed");
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the demo API.");
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setAuditMessage("");
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await fetch(`${API}/upload`, { method: "POST", body });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Upload failed");
      setResult(data);
      setText(`[Uploaded File]: ${file.name}`);
      setAnswers({});
      setSelectedCaseId("");
      setPatientSection("home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  // Web Speech API Text-to-Speech
  function playSpeech(textToRead: string) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setAudioStatusText(lang === "hi" ? "इस ब्राउज़र में आवाज़ उपलब्ध नहीं है।" : "Audio speech is not supported in this browser.");
      return;
    }

    window.speechSynthesis.cancel();
    stopAudio();

    if (!textToRead.trim()) return;

    const utterance = new SpeechSynthesisUtterance(textToRead);
    currentUtteranceRef.current = utterance;

    // Detect voices
    const voices = window.speechSynthesis.getVoices();
    if (lang === "hi") {
      const hiVoice = voices.find((v) => v.lang.startsWith("hi") || v.name.toLowerCase().includes("hindi"));
      if (hiVoice) {
        utterance.voice = hiVoice;
        utterance.lang = hiVoice.lang;
      } else {
        utterance.lang = "hi-IN";
      }
    } else {
      const enVoice = voices.find((v) => v.lang === "en-IN" || v.lang.startsWith("en"));
      if (enVoice) {
        utterance.voice = enVoice;
        utterance.lang = enVoice.lang;
      } else {
        utterance.lang = "en-US";
      }
    }

    utterance.rate = 0.95; // Slightly slower for patient clarity

    utterance.onstart = () => {
      setIsPlayingAudio(true);
      setAudioStatusText(lang === "hi" ? "🔊 आवाज़ चल रही है..." : "🔊 Playing audio...");
    };

    utterance.onend = () => {
      setIsPlayingAudio(false);
      setAudioStatusText(lang === "hi" ? "आवाज़ पूरी हुई।" : "Audio finished.");
    };

    utterance.onerror = () => {
      setIsPlayingAudio(false);
      setAudioStatusText(
        lang === "hi"
          ? "आवाज़ की सुविधा आपके डिवाइस और ब्राउज़र पर निर्भर करती है।"
          : "Voice playback depends on available browser and device voices."
      );
    };

    window.speechSynthesis.speak(utterance);
  }

  function stopAudio() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);
    setAudioStatusText("");
  }

  function toggleSource(id: string) {
    setExpandedSources((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  async function runHallucinationSafetyTest() {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      const fakeCandidate = [
        {
          name: "Oxycodone",
          strength: "5 mg",
          dose: "1 tablet",
          frequency: "every 4 hours as needed",
        },
      ];
      const r = await fetch(`${API}/audit-output`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_text: text,
          candidate_medications: fakeCandidate,
        }),
      });
      const flags: SafetyFlag[] = await r.json();
      if (flags.length > 0) {
        setAuditMessage(
          lang === "hi"
            ? "🛡️ सुरक्षा जांच सफल: 'Oxycodone' को रोका गया क्योंकि यह मूल कागज़ में नहीं लिखा है!"
            : "🛡️ Safety Check Succeeded: Blocked unsupported medication 'Oxycodone' not documented in the source text!"
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audit test failed");
    } finally {
      setBusy(false);
    }
  }

  const currentTestCase = testCases.find((tc) => tc.id === selectedCaseId);

  // Conversational text for patient overview audio
  function getOverviewSpeechText() {
    if (!result) return "";
    if (lang === "hi") {
      let overview = "Going Home Right mein aapka swagat hai. ";
      overview += `Aapke nirdesh ke anusaar, kul ${result.medications.length} dawaiyan likhi hain. `;
      if (result.follow_ups.length > 0 && result.follow_ups[0].timing) {
        overview += `Doctor se agli mulaqat ${result.follow_ups[0].timing} ko hai. `;
      }
      if (result.summary.needsReviewCount > 0) {
        overview += "Dhyan dein: Kuch jaankari adhoori hai, kripya lene se pehle doctor se confirm karein. ";
      }
      return overview;
    } else {
      let overview = "Welcome to Going Home Right. ";
      overview += `You have ${result.medications.length} documented medications. `;
      if (result.follow_ups.length > 0 && result.follow_ups[0].timing) {
        overview += `Your doctor appointment is ${result.follow_ups[0].timing}. `;
      }
      if (result.summary.needsReviewCount > 0) {
        overview += "Notice: Some details need verification with your care team before taking action. ";
      }
      return overview;
    }
  }

  return (
    <main className="shell">
      {/* Top Header Bar */}
      <header className="top">
        <a className="brand" href="#" onClick={(e) => { e.preventDefault(); setPatientSection("home"); }}>
          <span className="brand-mark">a</span>
          <span>
            Going Home Right
            <small>{lang === "hi" ? "Ghar par dekhbhaal ki jaankari, aasaan bhasha mein" : "EVIDENCE-LINKED CARE COMPANION"}</small>
          </span>
        </a>

        <div className="top-controls">
          {/* Language Toggle */}
          <div className="lang-switcher">
            <button
              className={`lang-btn ${lang === "hi" ? "active" : ""}`}
              onClick={() => setLang("hi")}
              aria-label="Switch to Hindi"
            >
              हिंदी
            </button>
            <button
              className={`lang-btn ${lang === "en" ? "active" : ""}`}
              onClick={() => setLang("en")}
              aria-label="Switch to English"
            >
              English
            </button>
          </div>

          {/* Mode Switcher */}
          <button
            className={`mode-toggle-btn ${viewMode === "technical" ? "active-tech" : ""}`}
            onClick={() => {
              setViewMode(viewMode === "patient" ? "technical" : "patient");
              setPatientSection("home");
            }}
            aria-label="Toggle Technical / Patient Mode"
          >
            {viewMode === "patient" ? (
              <>⚙️ {lang === "hi" ? "तकनीकी डैशबोर्ड" : "Technical Dashboard"}</>
            ) : (
              <>👤 {lang === "hi" ? "मरीज़ का मोड" : "Patient Mode"}</>
            )}
          </button>
        </div>
      </header>

      {/* Global Synthetic Demo Tag & Test Case Quick Selector Bar */}
      <section className="case-selector-bar">
        <div className="case-bar-left">
          <span className="demo-tag">
            <i /> {lang === "hi" ? "सिंथेटिक डेमो (काल्पनिक डेटा)" : "SYNTHETIC DEMO ONLY"}
          </span>
          <label htmlFor="testCaseSelect" className="case-label">
            {lang === "hi" ? "मरीज़ का केस चुनें:" : "Select Test Case:"}
          </label>
        </div>
        <select
          id="testCaseSelect"
          className="case-dropdown"
          value={selectedCaseId}
          onChange={(e) => {
            const found = testCases.find((c) => c.id === e.target.value);
            if (found) selectTestCase(found);
          }}
        >
          {testCases.map((tc, idx) => (
            <option key={tc.id} value={tc.id}>
              Case {idx + 1}: {tc.title}
            </option>
          ))}
        </select>
      </section>

      {/* Audio Status Toast Bar */}
      {audioStatusText && (
        <div className="audio-toast">
          <span>{audioStatusText}</span>
          {isPlayingAudio && (
            <button className="stop-speech-mini" onClick={stopAudio}>
              ⏹️ {lang === "hi" ? "रोकें (Stop)" : "Stop Audio"}
            </button>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* EXPERIENCE A: PATIENT & CAREGIVER EXPERIENCE (DEFAULT)     */}
      {/* ========================================================= */}
      {viewMode === "patient" && (
        <div className="patient-container">
          {/* 1. Patient Landing View */}
          {patientSection === "home" && (
            <section className="patient-home">
              <div className="patient-hero">
                <span className="eyebrow-patient">
                  {lang === "hi" ? "नमस्ते · आपके डिस्चार्ज के आसान निर्देश" : "WELCOME · SIMPLE DISCHARGE INSTRUCTIONS"}
                </span>
                <h1>
                  {lang === "hi" ? (
                    <>
                      Going Home Right
                      <br />
                      <em>घर पर देखभाल की जानकारी, आसान भाषा में।</em>
                    </>
                  ) : (
                    <>
                      Going Home Right
                      <br />
                      <em>Your care instructions, made easier to understand.</em>
                    </>
                  )}
                </h1>
                <p>
                  {lang === "hi"
                    ? "यह साथी आपको अस्पताल से मिली दवाइयों और डॉक्टर से मिलने के समय को आसान भाषा में समझाता है। कोई अंदाज़ा नहीं — सब कुछ आपके कागज़ से जुड़ा है।"
                    : "This companion explains your discharge medications, doctor appointments, and warning signs in plain language. Everything is tied directly to your paperwork."}
                </p>

                {/* Audio Overview Button */}
                <div className="audio-action-row">
                  {!isPlayingAudio ? (
                    <button
                      className="patient-audio-btn large"
                      onClick={() => playSpeech(getOverviewSpeechText())}
                    >
                      🔊 {lang === "hi" ? "पूरा सारांश सुनकर समझें" : "Listen to Overview"}
                    </button>
                  ) : (
                    <button className="patient-audio-btn stop large" onClick={stopAudio}>
                      ⏹️ {lang === "hi" ? "आवाज़ रोकें (Stop)" : "Stop Audio"}
                    </button>
                  )}
                  <span className="voice-note">
                    {lang === "hi" ? "ⓘ आवाज़ की सुविधा आपके डिवाइस पर निर्भर करती है" : "ⓘ Speech playback depends on device voices"}
                  </span>
                </div>
              </div>

              {/* 4 Prominent Action Tiles */}
              <div className="patient-tiles-grid">
                {/* Tile 1: Medicines */}
                <button
                  className="patient-tile med-tile"
                  onClick={() => setPatientSection("medicines")}
                >
                  <div className="tile-icon-box">💊</div>
                  <div className="tile-text">
                    <h2>{lang === "hi" ? "मेरी दवाइयां" : "My Medicines"}</h2>
                    <p>
                      {lang === "hi"
                        ? `दवाई कैसे और कब लेनी है (${result?.medications.length || 0} दवाइयां)`
                        : `How and when to take your medicines (${result?.medications.length || 0} items)`}
                    </p>
                  </div>
                  <span className="tile-arrow">→</span>
                </button>

                {/* Tile 2: Doctor Visit */}
                <button
                  className="patient-tile visit-tile"
                  onClick={() => setPatientSection("followup")}
                >
                  <div className="tile-icon-box">🩺</div>
                  <div className="tile-text">
                    <h2>{lang === "hi" ? "डॉक्टर से मुलाक़ात" : "Doctor Visit"}</h2>
                    <p>
                      {lang === "hi"
                        ? result?.follow_ups[0]?.timing
                          ? `अगली तारीख: ${result.follow_ups[0].timing}`
                          : "कब और कहाँ जाना है"
                        : result?.follow_ups[0]?.timing
                        ? `Appointment: ${result.follow_ups[0].timing}`
                        : "When and where to go for follow-up"}
                    </p>
                  </div>
                  <span className="tile-arrow">→</span>
                </button>

                {/* Tile 3: Home Care */}
                <button
                  className="patient-tile care-tile"
                  onClick={() => setPatientSection("homecare")}
                >
                  <div className="tile-icon-box">🏠</div>
                  <div className="tile-text">
                    <h2>{lang === "hi" ? "घर पर देखभाल" : "Home Care"}</h2>
                    <p>
                      {lang === "hi"
                        ? `घाव, खाना-पीना और आराम के नियम (${result?.care_instructions.length || 0})`
                        : `Wound care, diet, and rest guidelines (${result?.care_instructions.length || 0})`}
                    </p>
                  </div>
                  <span className="tile-arrow">→</span>
                </button>

                {/* Tile 4: I Need Help / Warning Signs */}
                <button
                  className="patient-tile help-tile"
                  onClick={() => setPatientSection("help")}
                >
                  <div className="tile-icon-box">🆘</div>
                  <div className="tile-text">
                    <h2>{lang === "hi" ? "मुझे मदद चाहिए" : "I Need Help"}</h2>
                    <p>
                      {lang === "hi"
                        ? "खतरे के लक्षण और अस्पताल के नंबर"
                        : "Warning signs, when to call, and clinic contacts"}
                    </p>
                  </div>
                  <span className="tile-arrow">→</span>
                </button>
              </div>

              {/* Action Tile 5: Teach-Back Understanding Check */}
              <div className="teach-back-banner">
                <div className="tb-content">
                  <span className="tb-badge">✍️ {lang === "hi" ? "जाँचें और समझें" : "Teach-Back Check"}</span>
                  <h3>{lang === "hi" ? "क्या आपको सब समझ आ गया?" : "Let's Check What's Clear"}</h3>
                  <p>
                    {lang === "hi"
                      ? "3 छोटे सवाल जो आपको पक्का करने में मदद करेंगे कि दवाइयां और तारीखें सही समझी हैं।"
                      : "A quick 3-question understanding check based on your discharge instructions."}
                  </p>
                </div>
                <button
                  className="tb-start-btn"
                  onClick={() => {
                    setCurrentQuizIdx(0);
                    setPatientSection("teachback");
                  }}
                >
                  {lang === "hi" ? "समझ की जाँच शुरू करें →" : "Check Understanding →"}
                </button>
              </div>

              {/* Simple Safety Note */}
              <aside className="patient-safety-box">
                <span className="safety-icon">✳</span>
                <div>
                  <strong>{lang === "hi" ? "अंदाज़ा मत लगाइए" : "Never Guess Your Instructions"}</strong>
                  <p>
                    {lang === "hi"
                      ? "अगर कोई जानकारी कागज़ पर साफ़ नहीं है, तो अपने डॉक्टर या फार्मासिस्ट से पूछकर पक्का करें। यह ऐप सिर्फ़ कागज़ में लिखी बात दिखाता है।"
                      : "If any instruction is unclear or missing, confirm with your doctor or pharmacist. This tool only organizes what is documented."}
                  </p>
                </div>
              </aside>
            </section>
          )}

          {/* 2. Patient Medications Screen */}
          {patientSection === "medicines" && (
            <section className="patient-subscreen">
              <div className="subscreen-header">
                <button className="back-btn" onClick={() => setPatientSection("home")}>
                  ← {lang === "hi" ? "मुख्य पृष्ठ (Home)" : "Back to Home"}
                </button>
                <div className="subscreen-title">
                  <h1>💊 {lang === "hi" ? "मेरी दवाइयां" : "My Medicines"}</h1>
                  <p>
                    {lang === "hi"
                      ? "हर दवाई के आगे लिखा है कि वह कितनी और कब लेनी है।"
                      : "Simple instructions for each medication as written in your paperwork."}
                  </p>
                </div>
              </div>

              {result && result.medications.length > 0 ? (
                <div className="patient-cards-list">
                  {result.medications.map((med, idx) => {
                    const speechText =
                      lang === "hi"
                        ? med.patient_summary_hi || `${med.name}: ${med.raw_text}`
                        : med.patient_summary_en || `${med.name}: ${med.raw_text}`;
                    const isExp = !!expandedSources[`pmed-${idx}`];

                    return (
                      <article key={idx} className={`patient-card ${med.status === "review" ? "needs-attention" : ""}`}>
                        <div className="pcard-top">
                          <h2 className="pcard-title">{med.name}</h2>
                          <span className={`pcard-badge ${med.status}`}>
                            {med.status === "review"
                              ? lang === "hi" ? "⚠ जानकारी अधूरी है" : "⚠ Needs Verification"
                              : lang === "hi" ? "✓ कागज़ में दर्ज" : "✓ Documented"}
                          </span>
                        </div>

                        {/* Conversational summary */}
                        <div className="pcard-summary">
                          <strong>{lang === "hi" ? "दवाई कैसे लेनी है:" : "How to take:"}</strong>
                          <p>{lang === "hi" ? med.patient_summary_hi : med.patient_summary_en}</p>
                        </div>

                        {/* Details grid */}
                        <div className="pcard-details-grid">
                          <div>
                            <span>{lang === "hi" ? "दवाई की ताक़त (Strength):" : "Strength:"}</span>
                            <b>{med.strength || (lang === "hi" ? "लिखी नहीं है (Ask Doctor)" : "Not documented")}</b>
                          </div>
                          <div>
                            <span>{lang === "hi" ? "कितनी लेनी है (How much):" : "How much:"}</span>
                            <b>{med.dose || (lang === "hi" ? "लिखी नहीं है" : "Not documented")}</b>
                          </div>
                          <div>
                            <span>{lang === "hi" ? "दिन में कितनी बार:" : "How often:"}</span>
                            <b>{med.frequency || (lang === "hi" ? "लिखी नहीं है" : "Not documented")}</b>
                          </div>
                          <div>
                            <span>{lang === "hi" ? "दिन का समय:" : "Time of day:"}</span>
                            <b style={{ textTransform: "capitalize" }}>
                              {med.timing_slot === "unspecified"
                                ? lang === "hi" ? "बोतल पर लिखे अनुसार" : "As documented on bottle"
                                : med.timing_slot.replace("_", " ")}
                            </b>
                          </div>
                          {med.duration && (
                            <div>
                              <span>{lang === "hi" ? "कितने दिनों तक:" : "Duration:"}</span>
                              <b>{med.duration}</b>
                            </div>
                          )}
                        </div>

                        {/* Critical safety alert if missing/conflicting */}
                        {med.status === "review" && (
                          <div className="patient-warning-banner">
                            <strong>{lang === "hi" ? "⚠ ध्यान दें:" : "⚠ Important:"}</strong>
                            <p>
                              {lang === "hi"
                                ? med.safety_alert_hi || "इस दवाई की कुछ ज़रूरी जानकारी लिखी नहीं है। कृपया दवाई लेने से पहले डॉक्टर या फार्मासिस्ट से कन्फर्म करें।"
                                : med.safety_alert_en || "Some important information about this medicine is missing. Please confirm with your doctor or pharmacist before acting on the unclear instruction."}
                            </p>
                          </div>
                        )}

                        {/* Audio and source buttons */}
                        <div className="pcard-actions">
                          <button
                            className="listen-chip-btn"
                            onClick={() => playSpeech(speechText)}
                          >
                            🔊 {lang === "hi" ? "दवाई की जानकारी सुनें" : "Listen to this medicine"}
                          </button>
                          <button
                            className="source-toggle-btn"
                            onClick={() => toggleSource(`pmed-${idx}`)}
                          >
                            {isExp
                              ? lang === "hi" ? "कागज़ की पंक्ति छुपाएं" : "Hide source passage"
                              : lang === "hi" ? "Yeh kahan likha hai? (यह कहाँ लिखा है?)" : "Where is this written?"}
                          </button>
                        </div>

                        {/* Expandable original source quotation */}
                        {isExp && (
                          <blockquote className="verbatim-source-box">
                            <span className="vtag">{lang === "hi" ? "कागज़ पर लिखी असली पंक्ति:" : "Original Documented Line:"}</span>
                            <p>{med.source_passage}</p>
                          </blockquote>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-patient-box">
                  <p>{lang === "hi" ? "कागज़ में कोई दवाई नहीं मिली।" : "No medications were documented in this paperwork."}</p>
                </div>
              )}
            </section>
          )}

          {/* 3. Patient Doctor Visit Screen */}
          {patientSection === "followup" && (
            <section className="patient-subscreen">
              <div className="subscreen-header">
                <button className="back-btn" onClick={() => setPatientSection("home")}>
                  ← {lang === "hi" ? "मुख्य पृष्ठ (Home)" : "Back to Home"}
                </button>
                <div className="subscreen-title">
                  <h1>🩺 {lang === "hi" ? "डॉक्टर से मुलाक़ात" : "Doctor Visit"}</h1>
                  <p>
                    {lang === "hi"
                      ? "डिस्चार्ज के बाद डॉक्टर से कब और कहाँ मिलना है।"
                      : "Follow-up schedule and clinic appointments documented in your paperwork."}
                  </p>
                </div>
              </div>

              {result && result.follow_ups.length > 0 ? (
                <div className="patient-cards-list">
                  {result.follow_ups.map((fu, idx) => {
                    const speechText =
                      lang === "hi"
                        ? `${fu.patient_summary_hi || fu.raw_text}. ${fu.contact ? "Phone number: " + fu.contact : ""}`
                        : `${fu.patient_summary_en || fu.raw_text}. ${fu.contact ? "Contact: " + fu.contact : ""}`;
                    const isExp = !!expandedSources[`pfu-${idx}`];

                    return (
                      <article key={idx} className={`patient-card ${fu.timing_missing ? "needs-attention" : ""}`}>
                        <div className="pcard-top">
                          <h2 className="pcard-title">
                            {fu.provider_or_clinic || (lang === "hi" ? "क्लिनिक विज़िट" : "Clinic Visit")}
                          </h2>
                          <span className={`pcard-badge ${fu.timing_missing ? "review" : "documented"}`}>
                            {fu.timing_missing
                              ? lang === "hi" ? "तारीख गायब है" : "Missing Timing"
                              : lang === "hi" ? "तय मुलाक़ात" : "Scheduled"}
                          </span>
                        </div>

                        {/* Timing explanation */}
                        <div className="pcard-summary">
                          <strong>{lang === "hi" ? "मुलाक़ात की तारीख:" : "Appointment Schedule:"}</strong>
                          <p style={{ fontSize: "17px", fontWeight: 600, color: "var(--green)" }}>
                            {fu.timing
                              ? fu.timing
                              : (lang === "hi" ? "तारीख लिखी नहीं है" : "Date or time is not documented")}
                          </p>
                        </div>

                        {/* Missing timing alert */}
                        {fu.timing_missing && (
                          <div className="patient-warning-banner">
                            <strong>{lang === "hi" ? "⚠ ध्यान दें:" : "⚠ Notice:"}</strong>
                            <p>
                              {lang === "hi"
                                ? fu.timing_alert_hi || "मुलाक़ात की तारीख या समय नहीं लिखा है। कृपया क्लिनिक से पूछें।"
                                : fu.timing_alert_en || "The appointment date or time is not documented. Please contact the clinic to confirm."}
                            </p>
                          </div>
                        )}

                        {/* Contact phone */}
                        {fu.contact && (
                          <div className="patient-contact-pill">
                            <span>📞 {lang === "hi" ? "फ़ोन नंबर:" : "Phone:"}</span>
                            <b>{fu.contact}</b>
                          </div>
                        )}

                        {/* Preparation instructions */}
                        {fu.prep_instructions && fu.prep_instructions.length > 0 && (
                          <div className="patient-prep-box">
                            <strong>{lang === "hi" ? "📋 जाने से पहले की तैयारी:" : "📋 What to bring & prepare:"}</strong>
                            <ul>
                              {fu.prep_instructions.map((p, pIdx) => (
                                <li key={pIdx}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Action buttons */}
                        <div className="pcard-actions">
                          <button
                            className="listen-chip-btn"
                            onClick={() => playSpeech(speechText)}
                          >
                            🔊 {lang === "hi" ? "मुलाक़ात की जानकारी सुनें" : "Listen to appointment"}
                          </button>
                          <button
                            className="source-toggle-btn"
                            onClick={() => toggleSource(`pfu-${idx}`)}
                          >
                            {isExp
                              ? lang === "hi" ? "कागज़ की पंक्ति छुपाएं" : "Hide source passage"
                              : lang === "hi" ? "Yeh kahan likha hai? (यह कहाँ लिखा है?)" : "Where is this written?"}
                          </button>
                        </div>

                        {isExp && (
                          <blockquote className="verbatim-source-box">
                            <span className="vtag">{lang === "hi" ? "कागज़ पर लिखी असली पंक्ति:" : "Original Documented Line:"}</span>
                            <p>{fu.source_passage}</p>
                          </blockquote>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-patient-box">
                  <p>{lang === "hi" ? "कागज़ में अगली मुलाक़ात का कोई ज़िक्र नहीं है।" : "No follow-up appointments were documented in this paperwork."}</p>
                </div>
              )}
            </section>
          )}

          {/* 4. Patient Home Care Screen */}
          {patientSection === "homecare" && (
            <section className="patient-subscreen">
              <div className="subscreen-header">
                <button className="back-btn" onClick={() => setPatientSection("home")}>
                  ← {lang === "hi" ? "मुख्य पृष्ठ (Home)" : "Back to Home"}
                </button>
                <div className="subscreen-title">
                  <h1>🏠 {lang === "hi" ? "घर पर देखभाल" : "Home Care"}</h1>
                  <p>
                    {lang === "hi"
                      ? "घाव, खाना-पीना और आराम के निर्देश जो कागज़ में लिखे हैं।"
                      : "Documented guidelines for wound care, diet, and recovery."}
                  </p>
                </div>
              </div>

              {result && result.care_instructions.length > 0 ? (
                <div className="patient-cards-list">
                  {result.care_instructions.map((ci, idx) => {
                    const speechText =
                      lang === "hi" ? ci.patient_summary_hi || ci.instruction : ci.patient_summary_en || ci.instruction;
                    const isExp = !!expandedSources[`pci-${idx}`];

                    return (
                      <article key={idx} className="patient-card">
                        <div className="pcard-top">
                          <h2 className="pcard-title">{ci.category}</h2>
                        </div>
                        <p className="pcard-main-text">{ci.instruction}</p>

                        <div className="pcard-actions">
                          <button
                            className="listen-chip-btn"
                            onClick={() => playSpeech(speechText)}
                          >
                            🔊 {lang === "hi" ? "निर्देश सुनें" : "Listen to instruction"}
                          </button>
                          <button
                            className="source-toggle-btn"
                            onClick={() => toggleSource(`pci-${idx}`)}
                          >
                            {isExp
                              ? lang === "hi" ? "कागज़ की पंक्ति छुपाएं" : "Hide source passage"
                              : lang === "hi" ? "Yeh kahan likha hai? (यह कहाँ लिखा है?)" : "Where is this written?"}
                          </button>
                        </div>

                        {isExp && (
                          <blockquote className="verbatim-source-box">
                            <span className="vtag">{lang === "hi" ? "कागज़ पर लिखी असली पंक्ति:" : "Original Documented Line:"}</span>
                            <p>{ci.source_passage}</p>
                          </blockquote>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-patient-box">
                  <p>{lang === "hi" ? "कागज़ में घर पर देखभाल का कोई अलग निर्देश नहीं लिखा है।" : "No specific home care instructions were documented in this paperwork."}</p>
                </div>
              )}
            </section>
          )}

          {/* 5. Patient Help & Safety Screen */}
          {patientSection === "help" && (
            <section className="patient-subscreen">
              <div className="subscreen-header">
                <button className="back-btn" onClick={() => setPatientSection("home")}>
                  ← {lang === "hi" ? "मुख्य पृष्ठ (Home)" : "Back to Home"}
                </button>
                <div className="subscreen-title">
                  <h1>🆘 {lang === "hi" ? "मुझे मदद चाहिए" : "I Need Help & Safety"}</h1>
                  <p>
                    {lang === "hi"
                      ? "खतरे के लक्षण और क्या करना चाहिए।"
                      : "Warning signs, urgent actions, and who to contact."}
                  </p>
                </div>
              </div>

              {/* Supportive advice banner */}
              <div className="patient-support-banner">
                <span className="support-icon">💡</span>
                <div>
                  <strong>{lang === "hi" ? "दवाई या पर्चा समझ नहीं आ रहा?" : "Not sure what an instruction means?"}</strong>
                  <p>
                    {lang === "hi"
                      ? "दवाई की जानकारी समझ नहीं आ रही? अंदाज़ा मत लगाइए। अपने डॉक्टर, फार्मासिस्ट या अस्पताल की केयर टीम से पूछें।"
                      : "Not sure what an instruction means? Please do not guess. Contact your doctor, pharmacist, or hospital care team."}
                  </p>
                </div>
              </div>

              {/* Documented Phone Contact */}
              {result?.follow_ups.find((f) => f.contact) && (
                <div className="verified-contact-card">
                  <span className="contact-icon">📞</span>
                  <div>
                    <strong>{lang === "hi" ? "अस्पताल का दर्ज किया गया फ़ोन नंबर:" : "Verified Hospital Contact:"}</strong>
                    <h2 className="contact-number">{result.follow_ups.find((f) => f.contact)?.contact}</h2>
                    <p>{lang === "hi" ? "संदेह होने पर इस नंबर पर कॉल करके पूछें।" : "Call this number if you have questions about your care."}</p>
                  </div>
                </div>
              )}

              {/* Warning signs cards */}
              {result && result.warning_signs.length > 0 && (
                <div className="patient-cards-list">
                  {result.warning_signs.map((ws, idx) => {
                    const isEmergency = ws.severity === "urgent_emergency";
                    const speechText =
                      lang === "hi"
                        ? ws.patient_summary_hi || `${ws.sign}. Turant madad lein.`
                        : ws.patient_summary_en || `${ws.sign}. Seek care.`;
                    const isExp = !!expandedSources[`pws-${idx}`];

                    return (
                      <article
                        key={idx}
                        className={`patient-card ${isEmergency ? "urgent-card" : "clinic-call-card"}`}
                      >
                        <div className="pcard-top">
                          <span className={`warning-type-tag ${ws.severity}`}>
                            {isEmergency
                              ? lang === "hi" ? "🚨 तुरंत अस्पताल जाएं / 911" : "🚨 EMERGENCY: Seek Immediate Care"
                              : lang === "hi" ? "📞 केयर टीम को फ़ोन करें" : "📞 Call Care Team"}
                          </span>
                        </div>
                        <h2 className="pcard-title" style={{ marginTop: "8px" }}>
                          {ws.sign}
                        </h2>
                        <p className="pcard-main-text">
                          <strong>{lang === "hi" ? "क्या करें:" : "Action:"}</strong> {ws.action}
                        </p>

                        <div className="pcard-actions">
                          <button
                            className="listen-chip-btn"
                            onClick={() => playSpeech(speechText)}
                          >
                            🔊 {lang === "hi" ? "यह लक्षण सुनें" : "Listen to warning sign"}
                          </button>
                          <button
                            className="source-toggle-btn"
                            onClick={() => toggleSource(`pws-${idx}`)}
                          >
                            {isExp
                              ? lang === "hi" ? "कागज़ की पंक्ति छुपाएं" : "Hide source passage"
                              : lang === "hi" ? "Yeh kahan likha hai? (यह कहाँ लिखा है?)" : "Where is this written?"}
                          </button>
                        </div>

                        {isExp && (
                          <blockquote className="verbatim-source-box">
                            <span className="vtag">{lang === "hi" ? "कागज़ पर लिखी असली पंक्ति:" : "Original Documented Line:"}</span>
                            <p>{ws.source_passage}</p>
                          </blockquote>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* 6. Patient Teach-Back Comprehension Screen */}
          {patientSection === "teachback" && (
            <section className="patient-subscreen">
              <div className="subscreen-header">
                <button className="back-btn" onClick={() => setPatientSection("home")}>
                  ← {lang === "hi" ? "मुख्य पृष्ठ (Home)" : "Back to Home"}
                </button>
                <div className="subscreen-title">
                  <h1>✍️ {lang === "hi" ? "समझ की सरल जाँच" : "Teach-Back Check"}</h1>
                  <p>
                    {lang === "hi"
                      ? "एक-एक करके आसान सवाल। कोई परीक्षा नहीं है — बस पक्का कर रहे हैं।"
                      : "Simple questions one at a time to check that instructions are clear. Not a test."}
                  </p>
                </div>
              </div>

              {result && result.teach_back.length > 0 && (
                <div className="patient-quiz-wrapper">
                  {(() => {
                    const q = result.teach_back[currentQuizIdx];
                    if (!q) return null;
                    const questionText = lang === "hi" && q.question_hi ? q.question_hi : q.question;
                    const optionsList = lang === "hi" && q.options_hi && q.options_hi.length > 0 ? q.options_hi : q.options;
                    const explanationText = lang === "hi" && q.explanation_hi ? q.explanation_hi : q.explanation;
                    const selected = answers[q.id];
                    const hasAnswered = selected !== undefined;
                    const isCorrect = selected === q.correct_index;
                    const isIDontKnow = selected === optionsList.length - 1; // "I don't understand" option

                    return (
                      <div className="patient-question-card">
                        <div className="quiz-progress-bar">
                          <span>
                            {lang === "hi" ? `सवाल ${currentQuizIdx + 1} / ${result.teach_back.length}` : `Question ${currentQuizIdx + 1} of ${result.teach_back.length}`}
                          </span>
                        </div>

                        <h2 className="quiz-question-text">{questionText}</h2>

                        {/* Read question aloud */}
                        <div style={{ marginBottom: "16px" }}>
                          <button
                            className="listen-chip-btn"
                            onClick={() => playSpeech(questionText)}
                          >
                            🔊 {lang === "hi" ? "सवाल सुनें" : "Listen to question"}
                          </button>
                        </div>

                        {/* Large, accessible touch options */}
                        <div className="patient-options-stack">
                          {optionsList.map((opt, oIdx) => {
                            const isChosen = selected === oIdx;
                            let btnStyle = "patient-choice-btn";
                            if (hasAnswered) {
                              if (oIdx === q.correct_index) btnStyle += " choice-correct";
                              else if (isChosen) btnStyle += " choice-wrong";
                            }
                            return (
                              <button
                                key={oIdx}
                                className={btnStyle}
                                onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: oIdx }))}
                              >
                                <span className="choice-bullet">
                                  {hasAnswered && oIdx === q.correct_index ? "✓" : String.fromCharCode(65 + oIdx)}
                                </span>
                                <span className="choice-label">{opt}</span>
                              </button>
                            );
                          })}
                        </div>

                        {/* Supportive Feedback without blaming */}
                        {hasAnswered && (
                          <div className={`patient-feedback-box ${isCorrect ? "good" : "support"}`}>
                            <strong>
                              {isCorrect
                                ? lang === "hi" ? "✓ बहुत बढ़िया! सही समझा:" : "✓ Great! That matches your paperwork:"
                                : isIDontKnow
                                ? lang === "hi" ? "💡 कोई बात नहीं, समझना आसान बनाते हैं:" : "💡 No problem at all, let's make it clear:"
                                : lang === "hi" ? "ℹ कागज़ के अनुसार यह सही उत्तर है:" : "ℹ According to your discharge paperwork:"}
                            </strong>
                            <p>{explanationText}</p>
                            <blockquote className="tb-source-quote">
                              <span>{lang === "hi" ? "कागज़ का प्रमाण:" : "Evidence citation:"}</span> {q.source_passage}
                            </blockquote>
                          </div>
                        )}

                        {/* Next question navigation */}
                        <div className="quiz-nav-row">
                          {currentQuizIdx > 0 && (
                            <button
                              className="quiz-prev-btn"
                              onClick={() => setCurrentQuizIdx(currentQuizIdx - 1)}
                            >
                              ← {lang === "hi" ? "पिछला सवाल" : "Previous"}
                            </button>
                          )}
                          {currentQuizIdx < result.teach_back.length - 1 ? (
                            <button
                              className="quiz-next-btn"
                              onClick={() => setCurrentQuizIdx(currentQuizIdx + 1)}
                            >
                              {lang === "hi" ? "अगला सवाल →" : "Next Question →"}
                            </button>
                          ) : (
                            <button
                              className="quiz-next-btn finish"
                              onClick={() => setPatientSection("home")}
                            >
                              ✓ {lang === "hi" ? "जाँच पूरी हुई (Home)" : "Finish Check (Home)"}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}
            </section>
          )}

          {/* Prototype Clinical Disclaimer */}
          <div className="patient-disclaimer-card">
            <p>
              {lang === "hi"
                ? "यह एक सिंथेटिक-डेटा हैकथॉन प्रोटोटाइप है। यह कोई मेडिकल सलाह या डॉक्टर का विकल्प नहीं है। किसी भी सवाल या संदेह के लिए हमेशा अपने डॉक्टर या अस्पताल की टीम से पूछें।"
                : "This is a synthetic-data hackathon prototype for demonstration. It does not provide medical advice or diagnosis. Always confirm any unclear instructions with your clinical care team."}
            </p>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* EXPERIENCE B: TECHNICAL REVIEWER DASHBOARD                 */}
      {/* ========================================================= */}
      {viewMode === "technical" && (
        <section className="technical-container">
          {/* Dashboard Header Bar */}
          <div className="tech-dash-header">
            <div>
              <span className="step">ENGINEERING & REVIEWER VIEW</span>
              <h2>Going Home Right — Evidence-Linked Care Dashboard</h2>
              <p>Transparent deterministic parsing, clinical safety audits, and source-passage verification</p>
            </div>
            <button
              className="back-to-patient-btn"
              onClick={() => setViewMode("patient")}
            >
              👤 {lang === "hi" ? "मरीज़ के मोड में लौटें" : "Return to Patient Mode"}
            </button>
          </div>

          {/* Document Input & Controls Card */}
          <div className="input-card">
            <div className="card-head">
              <div>
                <span className="step">01</span>
                <div>
                  <h2>Document Input & Edge Case Testing</h2>
                  <p>10 Synthetic Clinical Edge Cases · PyMuPDF text PDF / .txt upload</p>
                </div>
              </div>
              <span className="lock">⌑ Fictional Data Only</span>
            </div>

            <div className="input-actions">
              <label className="upload">
                ↑ Upload .txt / text PDF (PyMuPDF)
                <input type="file" accept=".txt,.pdf" onChange={onFile} />
              </label>
              <button
                className="audit-sim-btn"
                onClick={runHallucinationSafetyTest}
                title="Test safety rule against hallucinated medications"
              >
                🛡️ Test Hallucination Filter
              </button>
            </div>

            <textarea
              value={text.startsWith("[Uploaded File]:") ? "" : text}
              onChange={(e) => {
                setText(e.target.value);
                setResult(null);
                setSelectedCaseId("");
              }}
              placeholder="Paste discharge instructions here…\n\nTip: Uses recognized headings: MEDICATIONS, FOLLOW-UP, WARNING SIGNS, CARE INSTRUCTIONS."
              aria-label="Discharge instructions"
            />

            {text.startsWith("[Uploaded File]:") && <div className="file-note">✓ {text}</div>}
            {auditMessage && <div className="audit-alert">{auditMessage}</div>}

            <div className="submit-row">
              <span>Designed to flag missing or conflicting information · Deterministic parsing</span>
              <button
                className="primary"
                onClick={() => analyzeTextDirectly(text, selectedCaseId)}
                disabled={busy || !text.trim() || text.startsWith("[Uploaded File]:")}
              >
                {busy ? "Auditing & Extracting…" : "Organize & Audit Instructions"}
                <span>→</span>
              </button>
            </div>

            {error && <div className="error">{error}</div>}
          </div>

          {/* Results Display */}
          {result && (
            <div className="results">
              {/* Counts */}
              <div className="counts">
                <div>
                  <b>{result.summary.medications}</b>
                  <span>MEDICATIONS</span>
                </div>
                <div>
                  <b>{result.summary.followUps}</b>
                  <span>FOLLOW-UPS</span>
                </div>
                <div>
                  <b>{result.summary.warningSigns}</b>
                  <span>WARNING SIGNS</span>
                </div>
                <div className="review-count">
                  <b>{result.summary.needsReviewCount}</b>
                  <span>NEEDS VERIFICATION</span>
                </div>
              </div>

              {/* Safety Flags Section */}
              {result.safety_flags.length > 0 && (
                <div className="flags-card">
                  <div className="flags-header">
                    <span className="warning-icon">⚠</span>
                    <div>
                      <h3>Needs Healthcare Team Verification ({result.safety_flags.length})</h3>
                      <p>Deterministic clinical safety flags. Clarify with prescribing physician before taking action.</p>
                    </div>
                  </div>
                  <div className="flag-items">
                    {result.safety_flags.map((flag, idx) => (
                      <div key={idx} className={`flag-box ${flag.severity}`}>
                        <div className="flag-top">
                          <span className={`flag-tag ${flag.severity}`}>
                            {flag.severity.toUpperCase()} · {flag.category.replace("_", " ").toUpperCase()}
                          </span>
                          <strong>{flag.title}</strong>
                        </div>
                        <p className="flag-msg">{flag.message}</p>
                        {flag.source_passage && (
                          <div className="flag-source">
                            <span>Source:</span> <code>{flag.source_passage}</code>
                          </div>
                        )}
                        <div className="flag-action">
                          <span>Action Required:</span> {flag.action_required}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Strict Time Slot Filter Pills */}
              <div className="section-card">
                <div className="section-head">
                  <h3>Documented Medications (Strict Time Slots)</h3>
                  <p>Organized into time slots only when explicitly supported by source text. No guessing.</p>
                </div>

                <div className="slot-pills">
                  <button className={activeSlot === "all" ? "active" : ""} onClick={() => setActiveSlot("all")}>
                    All ({result.medications.length})
                  </button>
                  <button className={activeSlot === "morning" ? "active" : ""} onClick={() => setActiveSlot("morning")}>
                    ☀️ Morning ({result.schedule.morning.length})
                  </button>
                  <button className={activeSlot === "afternoon" ? "active" : ""} onClick={() => setActiveSlot("afternoon")}>
                    ⛅ Afternoon ({result.schedule.afternoon.length})
                  </button>
                  <button className={activeSlot === "night" ? "active" : ""} onClick={() => setActiveSlot("night")}>
                    🌙 Bedtime ({result.schedule.night.length})
                  </button>
                  <button className={activeSlot === "as_needed" ? "active" : ""} onClick={() => setActiveSlot("as_needed")}>
                    ⚡ As Needed ({result.schedule.as_needed.length})
                  </button>
                  <button className={activeSlot === "frequency" ? "active" : ""} onClick={() => setActiveSlot("frequency")}>
                    📋 General Frequency ({result.schedule.documented_frequency.length})
                  </button>
                </div>

                <div className="med-grid">
                  {result.medications
                    .filter((med) => {
                      if (activeSlot === "all") return true;
                      if (activeSlot === "morning") return med.timing_slot === "morning";
                      if (activeSlot === "afternoon") return med.timing_slot === "afternoon";
                      if (activeSlot === "night") return med.timing_slot === "night";
                      if (activeSlot === "as_needed") return med.timing_slot === "as_needed";
                      if (activeSlot === "frequency") return med.timing_slot === "unspecified";
                      return true;
                    })
                    .map((med, idx) => {
                      const isExp = !!expandedSources[`tech-med-${idx}`];
                      return (
                        <article key={idx} className={`care-item ${med.status}`}>
                          <div className="item-top">
                            <span className="category medication">MEDICATION</span>
                            <span className={`status-badge ${med.status}`}>
                              {med.status === "review" ? "⚠ Needs Review" : "✓ Documented"}
                            </span>
                          </div>
                          <h4 className="med-title">{med.name}</h4>
                          <div className="med-details">
                            <div className="detail-item">
                              <span>Strength:</span> <b>{med.strength || "Unspecified"}</b>
                            </div>
                            <div className="detail-item">
                              <span>Dose:</span> <b>{med.dose || "Unspecified"}</b>
                            </div>
                            <div className="detail-item">
                              <span>Route:</span> <b>{med.route || "Unspecified"}</b>
                            </div>
                            <div className="detail-item">
                              <span>Frequency:</span> <b>{med.frequency || "Unspecified"}</b>
                            </div>
                            <div className="detail-item">
                              <span>Timing Slot:</span>{" "}
                              <b style={{ textTransform: "capitalize" }}>
                                {med.timing_slot === "unspecified" ? "As documented" : med.timing_slot.replace("_", " ")}
                              </b>
                            </div>
                          </div>

                          {med.review_reasons.length > 0 && (
                            <div className="review-box">
                              {med.review_reasons.map((r, i) => (
                                <p key={i}>• {r}</p>
                              ))}
                            </div>
                          )}

                          <button className="evidence-btn" onClick={() => toggleSource(`tech-med-${idx}`)}>
                            ⌕ {isExp ? "Hide Source Passage" : "View Source Passage"}
                          </button>

                          {isExp && (
                            <blockquote className="source-passage">
                              <span>Exact Documented Line:</span>
                              <p>{med.source_passage}</p>
                            </blockquote>
                          )}
                        </article>
                      );
                    })}
                </div>
              </div>

              {/* Follow-up Section */}
              {result.follow_ups.length > 0 && (
                <div className="section-card">
                  <div className="section-head">
                    <h3>Follow-up Appointments & Preparation Instructions</h3>
                  </div>
                  <div className="item-grid">
                    {result.follow_ups.map((fu, idx) => (
                      <article key={idx} className={`care-item ${fu.status}`}>
                        <div className="item-top">
                          <span className="category followup">FOLLOW-UP</span>
                          <span className={`status-badge ${fu.status}`}>
                            {fu.status === "review" ? "⚠ Needs Review" : "✓ Documented"}
                          </span>
                        </div>
                        <p className="item-main-text">{fu.raw_text}</p>
                        <div className="fu-meta">
                          {fu.timing && (
                            <div>
                              <span>Scheduled:</span> <b>{fu.timing}</b>
                            </div>
                          )}
                          {fu.contact && (
                            <div>
                              <span>Contact:</span> <b>{fu.contact}</b>
                            </div>
                          )}
                        </div>
                        {fu.prep_instructions && fu.prep_instructions.length > 0 && (
                          <div style={{ fontSize: "12px", color: "var(--green)", marginTop: "6px" }}>
                            <b>Prep:</b> {fu.prep_instructions.join("; ")}
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                </div>
              )}

              {/* Disclaimer */}
              <div className="disclaimer">{result.disclaimer}</div>
            </div>
          )}
        </section>
      )}

      {/* Footer */}
      <footer>
        <span>Going Home Right · AAYU 2026 Problem Statement T03</span>
        <span>Evidence-Linked Care Companion · Bilingual Voice-First Prototype</span>
      </footer>
    </main>
  );
}
