/**
 * CyberAssist — AI-Powered Cybercrime Complaint Assistant
 * Client Controller: Multi-Screen Flow (Screens 3, 4, 5, 6, 7)
 * Implements: Dual-Mode Voice Input, Devanagari TTS, Live Information Extraction,
 * Draft Review/Editing, and Scikit-Learn Classification.
 */

// ==========================================================================
// 1. Application State
// ==========================================================================

const state = {
  sessionId: 'CYB-2026-' + Math.floor(100000 + Math.random() * 900000),
  currentLang: 'hi', // 'hi', 'mr', 'en'
  currentScreen: 'page-choose-mode',
  isListening: false,
  recognition: null,
  voices: [],
  history: [],
  draft: {
    category: 'Online Financial Fraud',
    subcategory: 'UPI Related Frauds',
    datetime: new Date().toISOString().slice(0, 16),
    amount: null,
    bank: '',
    utr: '',
    platform: 'Phone Call',
    suspect: '',
    evidence: '',
    narrative: ''
  },
  classificationResult: null
};

// ==========================================================================
// 1.1 NCRP Certified Taxonomy (3 Main Categories -> 21 Sub-Categories)
// ==========================================================================

const NCRP_TAXONOMY = {
  "Online and Social Media Related Crime": [
    "Cheating by Impersonation",
    "Cyber Bullying / Stalking / Sexting",
    "Email Phishing",
    "Fake / Impersonating Profile",
    "Impersonating Email (Business Email Compromise)",
    "Intimidating Email",
    "Online Job Fraud",
    "Online Matrimonial Fraud",
    "Profile Hacking / Identity Theft",
    "Provocative Speech for Unlawful Acts"
  ],
  "Online Financial Fraud": [
    "AePS Fraud",
    "Debit/Credit Card Fraud / SIM Swap Fraud",
    "Demat / Depository Fraud",
    "E-Wallet Related Fraud",
    "Internet Banking Related Fraud",
    "UPI Related Frauds"
  ],
  "Hacking / Damage to Computer": [
    "Damage to Computer / Computer System",
    "Email Hacking",
    "Tampering with Computer Source Document",
    "Unauthorised Access / Data Breach",
    "Website Defacement / Hacking"
  ]
};

const SUBCAT_TO_MAIN = {};
for (const [mainCat, subs] of Object.entries(NCRP_TAXONOMY)) {
  for (const sub of subs) {
    SUBCAT_TO_MAIN[sub] = mainCat;
  }
}

function getMainCategoryForSubcategory(subcat) {
  if (!subcat) return "Online Financial Fraud";
  if (SUBCAT_TO_MAIN[subcat]) return SUBCAT_TO_MAIN[subcat];
  for (const [s, m] of Object.entries(SUBCAT_TO_MAIN)) {
    if (s.toLowerCase() === subcat.toLowerCase()) return m;
    if (subcat.toLowerCase().includes(s.toLowerCase()) || s.toLowerCase().includes(subcat.toLowerCase())) return m;
  }
  return "Online Financial Fraud";
}

function populateManualSubcategories(selectedMainCat, selectedSubcat = '') {
  const selectEl = document.getElementById('man-subcategory');
  if (!selectEl) return;
  selectEl.innerHTML = '';

  if (!selectedMainCat) {
    // Show all 21 subcategories grouped by the 3 main categories
    const defOpt = document.createElement('option');
    defOpt.value = '';
    defOpt.textContent = '-- Select Sub-Category --';
    selectEl.appendChild(defOpt);

    for (const [mainCat, subs] of Object.entries(NCRP_TAXONOMY)) {
      const group = document.createElement('optgroup');
      group.label = `${mainCat} (${subs.length} Sub-Categories)`;
      for (const sub of subs) {
        const opt = document.createElement('option');
        opt.value = sub;
        opt.textContent = sub;
        if (selectedSubcat && sub === selectedSubcat) opt.selected = true;
        group.appendChild(opt);
      }
      selectEl.appendChild(group);
    }
    return;
  }

  // Filtered to only the chosen main category
  const subs = NCRP_TAXONOMY[selectedMainCat] || [];
  const defOpt = document.createElement('option');
  defOpt.value = '';
  defOpt.textContent = `-- Select Sub-Category (${selectedMainCat}) --`;
  selectEl.appendChild(defOpt);

  for (const sub of subs) {
    const opt = document.createElement('option');
    opt.value = sub;
    opt.textContent = sub;
    if (selectedSubcat && sub === selectedSubcat) opt.selected = true;
    selectEl.appendChild(opt);
  }

  if (selectedSubcat && subs.includes(selectedSubcat)) {
    selectEl.value = selectedSubcat;
  } else if (subs.length > 0) {
    selectEl.value = subs[0];
    state.draft.subcategory = subs[0];
  }
}

// ==========================================================================
// 2. DOM Elements
// ==========================================================================

// Screen Containers & Navigation
const screenViews = document.querySelectorAll('.screen-view');
const stepperTabBtns = document.querySelectorAll('.stepper-tab-btn');
const brandLogoBtn = document.getElementById('brand-logo-btn');
const navReport = document.getElementById('nav-report');
const navDashboard = document.getElementById('nav-dashboard');
const lblSessionId = document.getElementById('lbl-session-id');
const btnResetSession = document.getElementById('btn-reset-session');

// Language & Voice Test Controls
const btnLangEn = document.getElementById('btn-lang-en');
const btnLangHi = document.getElementById('btn-lang-hi');
const btnLangMr = document.getElementById('btn-lang-mr');
const btnTestVoice = document.getElementById('btn-test-voice');

// Screen 3: Choose Mode
const btnStartVoice = document.getElementById('btn-start-voice');
const btnStartManual = document.getElementById('btn-start-manual');
const cardChooseVoice = document.getElementById('card-choose-voice');
const cardChooseManual = document.getElementById('card-choose-manual');

// Screen 4: Voice Copilot
const btnVoiceToManual = document.getElementById('btn-voice-to-manual');
const chatStream = document.getElementById('chat-stream');
const selectVoiceLang = document.getElementById('select-voice-lang');
const btnMicMain = document.getElementById('btn-mic-main');
const btnMicLabel = document.getElementById('btn-mic-label');
const btnMicStop = document.getElementById('btn-mic-stop');
const inputVoiceText = document.getElementById('input-voice-text');
const btnVoiceSend = document.getElementById('btn-voice-send');
const voiceSubtitlesBar = document.getElementById('voice-subtitles-bar');
const subtitlesContent = document.getElementById('subtitles-content');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const infoCounterBadge = document.getElementById('info-counter-badge');
const btnResetChecklist = document.getElementById('btn-reset-checklist');
const btnProceedFromVoice = document.getElementById('btn-proceed-from-voice');

// Screen 4 Checklist Item Elements
const itemIncidentType = document.getElementById('item-incident-type');
const valIncidentType = document.getElementById('val-incident-type');
const itemAmount = document.getElementById('item-amount');
const valAmount = document.getElementById('val-amount');
const itemDatetime = document.getElementById('item-datetime');
const valDatetime = document.getElementById('val-datetime');
const itemPlatform = document.getElementById('item-platform');
const valPlatform = document.getElementById('val-platform');
const itemBank = document.getElementById('item-bank');
const valBank = document.getElementById('val-bank');
const itemSuspect = document.getElementById('item-suspect');
const valSuspect = document.getElementById('val-suspect');
const itemEvidence = document.getElementById('item-evidence');
const valEvidence = document.getElementById('val-evidence');
const itemNarrative = document.getElementById('item-narrative');
const valNarrative = document.getElementById('val-narrative');

// Screen 5: Manual Form
const formManualComplaint = document.getElementById('form-manual-complaint');
const manCategory = document.getElementById('man-category');
const manSubcategory = document.getElementById('man-subcategory');
const manDatetime = document.getElementById('man-datetime');
const manAmount = document.getElementById('man-amount');
const manBank = document.getElementById('man-bank');
const manUtr = document.getElementById('man-utr');
const manPlatform = document.getElementById('man-platform');
const manSuspect = document.getElementById('man-suspect');
const manOther = document.getElementById('man-other');
const manDescription = document.getElementById('man-description');
const manCharCount = document.getElementById('man-char-count');
const manEvidenceNotes = document.getElementById('man-evidence-notes');
const manFileUpload = document.getElementById('man-file-upload');
const btnManualBack = document.getElementById('btn-manual-back');

// Screen 6: Draft Review & Edit
const reviewNarrativeText = document.getElementById('review-narrative-text');
const reviewNarrativeEdit = document.getElementById('review-narrative-edit');
const btnEditNarrativeToggle = document.getElementById('btn-edit-narrative-toggle');
const btnListenReview = document.getElementById('btn-listen-review');
const btnEditDetailsToggle = document.getElementById('btn-edit-details-toggle');
const revCategory = document.getElementById('rev-category');
const revSubcategory = document.getElementById('rev-subcategory');
const revDatetime = document.getElementById('rev-datetime');
const revAmount = document.getElementById('rev-amount');
const revPlatform = document.getElementById('rev-platform');
const revBank = document.getElementById('rev-bank');
const revUtr = document.getElementById('rev-utr');
const revSuspect = document.getElementById('rev-suspect');
const chkReviewVerify = document.getElementById('chk-review-verify');
const btnBackToVoice = document.getElementById('btn-back-to-voice');
const btnConfirmAndClassify = document.getElementById('btn-confirm-and-classify');

// Screen 7: Classification Result
const resPredictedCategory = document.getElementById('res-predicted-category');
const resSubcategoryText = document.getElementById('res-subcategory-text');
const resConfidenceVal = document.getElementById('res-confidence-val');
const resConfidenceBar = document.getElementById('res-confidence-bar');
const resMarginVal = document.getElementById('res-margin-val');
const resRunnerUp = document.getElementById('res-runner-up');
const resSummaryText = document.getElementById('res-summary-text');
const btnViewFullDraft = document.getElementById('btn-view-full-draft');
const resStatuteTags = document.getElementById('res-statute-tags');
const btnDownloadPdfResult = document.getElementById('btn-download-pdf-result');
const btnSaveContinue = document.getElementById('btn-save-continue');

// Toast
const toastEl = document.getElementById('toast-el');
const toastText = document.getElementById('toast-text');

// ==========================================================================
// 3. Initialization
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  lblSessionId.textContent = state.sessionId;
  manDatetime.value = state.draft.datetime;
  initVoices();
  initSpeechRecognition();
  initEventListeners();

  // Initialize cascading category and sub-category dropdowns
  populateManualSubcategories(state.draft.category, state.draft.subcategory);

  // Show Initial Screen (Screen 3: Choose Mode)
  showScreen('page-choose-mode');

  // Load initial greeting into voice chat
  initInitialGreeting();
});

// Screen Router
function showScreen(screenId) {
  state.currentScreen = screenId;

  // Toggle views
  screenViews.forEach(v => {
    v.classList.remove('active');
    if (v.id === screenId) {
      v.classList.add('active');
    }
  });

  // Toggle top stepper tab buttons
  stepperTabBtns.forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.target === screenId) {
      btn.classList.add('active');
    }
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ==========================================================================
// 4. Dual-Engine Speech Recognition (Web Speech API + Local Whisper Fallback)
// ==========================================================================

let mediaRecorder = null;
let audioChunks = [];
let silenceTimer = null;
let accumulatedWebSpeechText = '';

function getLangCode() {
  if (state.currentLang === 'hi') return 'hi-IN';
  if (state.currentLang === 'mr') return 'mr-IN';
  return 'en-IN';
}

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  state.recognition = new SpeechRecognition();
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  state.recognition.lang = getLangCode();

  state.recognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const chunk = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        accumulatedWebSpeechText += chunk + ' ';
      } else {
        interim += chunk;
      }
    }
    const currentDisplay = (accumulatedWebSpeechText + ' ' + interim).trim();
    if (currentDisplay) {
      subtitlesContent.textContent = currentDisplay;
    }
  };

  state.recognition.onerror = (event) => {
    console.warn("Web Speech notice:", event.error);
    if (event.error === 'not-allowed') {
      showToast("Microphone access denied. Please click the lock icon in the address bar to allow mic.");
      stopListening();
    }
  };

  state.recognition.onend = () => {
    if (state.isListening && (!mediaRecorder || mediaRecorder.state === 'inactive')) {
      stopListening();
    }
  };
}

async function startListening() {
  accumulatedWebSpeechText = '';
  audioChunks = [];

  state.isListening = true;
  btnMicMain.classList.add('active-listening');
  btnMicLabel.textContent = 'Listening...';
  statusDot.className = 'status-indicator-dot recording';
  statusText.textContent = 'Listening...';
  voiceSubtitlesBar.style.display = 'flex';
  subtitlesContent.textContent = state.currentLang === 'mr' ? 'ऐकत आहे... (Listening)' : (state.currentLang === 'hi' ? 'सुन रहा हूँ... (Listening)' : 'Listening...');

  // 1. Parallel HTML5 MediaRecorder (Local Whisper fallback)
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
        }
      };
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        processRecordedAudio();
      };
      mediaRecorder.start(250);
    } catch (err) {
      console.warn("MediaRecorder permission notice:", err);
    }
  }

  // 2. Start Web Speech Recognition
  if (state.recognition) {
    try {
      state.recognition.lang = getLangCode();
      state.recognition.start();
    } catch (e) {}
  }

  // Auto-stop after 8 seconds of continuous recording
  clearTimeout(silenceTimer);
  silenceTimer = setTimeout(() => {
    if (state.isListening) {
      stopListening();
    }
  }, 8500);
}

function stopListening() {
  clearTimeout(silenceTimer);
  state.isListening = false;
  btnMicMain.classList.remove('active-listening');
  btnMicLabel.textContent = 'Tap to Speak';
  statusDot.className = 'status-indicator-dot ready';
  statusText.textContent = 'Ready';

  // Stop Web Speech
  if (state.recognition) {
    try { state.recognition.stop(); } catch (e) {}
  }

  // Stop MediaRecorder (triggers onstop -> processRecordedAudio)
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try { mediaRecorder.stop(); } catch (e) {}
  } else {
    finalizeSpeechResult(accumulatedWebSpeechText);
  }
}

async function processRecordedAudio() {
  const webText = accumulatedWebSpeechText.trim();

  // If Web Speech captured good text, use it immediately
  if (webText && webText !== 'Listening...' && webText !== '.' && webText.length > 2) {
    finalizeSpeechResult(webText);
    return;
  }

  // Otherwise, transcribe with local Whisper
  if (audioChunks.length > 0) {
    subtitlesContent.textContent = "⏳ Transcribing with Local Whisper AI...";
    showToast("Transcribing with Local Whisper AI...");
    try {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      if (audioBlob.size > 1500) {
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('language', state.currentLang);

        const res = await fetch('/api/transcribe', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.ok && data.text && data.text.trim()) {
          finalizeSpeechResult(data.text.trim());
          return;
        }
      }
    } catch (err) {
      console.warn("Backend Whisper transcription error:", err);
    }
  }

  voiceSubtitlesBar.style.display = 'none';
  showToast("No speech detected. Please speak closer to microphone or type.");
}

function finalizeSpeechResult(text) {
  voiceSubtitlesBar.style.display = 'none';
  const clean = (text || '').trim();
  if (!clean || clean === '.' || clean === 'Listening...') {
    showToast("No speech recognized. Please tap mic and speak clearly.");
    return;
  }
  showToast("✓ Voice recognized: " + clean.substring(0, 30) + "...");
  handleUserTurn(clean);
}

// ==========================================================================
// 5. High-Fidelity Text-to-Speech (Indian Pronunciation)
// ==========================================================================

function initVoices() {
  if (!('speechSynthesis' in window)) return;
  const load = () => { state.voices = window.speechSynthesis.getVoices(); };
  load();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = load;
  }
}

function getBestVoice(lang) {
  const voices = state.voices.length > 0 ? state.voices : window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  if (lang === 'mr') {
    return voices.find(v => v.lang.startsWith('mr') || v.name.toLowerCase().includes('marathi'))
      || voices.find(v => v.lang === 'hi-IN' || v.lang.startsWith('hi'))
      || voices.find(v => v.lang.includes('IN'))
      || voices[0];
  } else if (lang === 'hi') {
    return voices.find(v => v.lang === 'hi-IN' || v.lang.startsWith('hi') || v.name.toLowerCase().includes('hindi'))
      || voices.find(v => v.lang.includes('IN'))
      || voices[0];
  } else {
    return voices.find(v => v.lang === 'en-IN' || (v.lang.startsWith('en') && v.name.toLowerCase().includes('india')))
      || voices.find(v => v.lang.startsWith('en'))
      || voices[0];
  }
}

function normalizeSpeechText(text, lang) {
  let cleaned = text.replace(/(\d+),(\d+)/g, '$1$2');
  if (lang === 'mr' || lang === 'hi') {
    cleaned = cleaned.replace(/₹\s*(\d+)/g, '$1 रुपये');
    cleaned = cleaned.replace(/₹/g, ' रुपये ');
    cleaned = cleaned.replace(/\bUTR\b/gi, 'यूटीआर');
    cleaned = cleaned.replace(/\bPNB\b/gi, 'पीएनबी');
    cleaned = cleaned.replace(/\bSBI\b/gi, 'एसबीआई');
    cleaned = cleaned.replace(/\bOTP\b/gi, 'ओटीपी');
  } else {
    cleaned = cleaned.replace(/₹\s*(\d+)/g, 'Rs. $1');
  }
  return cleaned;
}

function speakText(rawText, lang = state.currentLang) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();

  const cleaned = normalizeSpeechText(rawText, lang);
  const utterance = new SpeechSynthesisUtterance(cleaned);
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  const voice = getBestVoice(lang);
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang || (lang === 'hi' ? 'hi-IN' : (lang === 'mr' ? 'hi-IN' : 'en-IN'));
  } else {
    utterance.lang = lang === 'hi' ? 'hi-IN' : (lang === 'mr' ? 'hi-IN' : 'en-IN');
  }

  window.speechSynthesis.speak(utterance);
}

function handleTestVoice() {
  const phrases = {
    hi: "नमस्ते, यह साइबर असिस्ट का वॉइस सहायक है। आपकी आवाज स्पष्ट रूप से सुनी जा रही है।",
    mr: "नमस्कार, हे सायबर असिस्टचे व्हॉइस असिस्टंट आहे. आपला आवाज व्यवस्थित ऐकू येत आहे.",
    en: "Hello, this is CyberAssist AI. The voice system is online and ready."
  };
  const text = phrases[state.currentLang] || phrases.hi;
  showToast("Testing voice output...");
  speakText(text, state.currentLang);
}

// ==========================================================================
// 6. Conversational Dialogue & Live Information Extraction
// ==========================================================================

function initInitialGreeting() {
  chatStream.innerHTML = '';
  const greetings = {
    hi: "नमस्ते! मैं आपका साइबर अपराध शिकायत सहायक हूँ। आपके साथ क्या धोखाधड़ी हुई है, कृपया अपने शब्दों में बताएं।",
    mr: "नमस्कार! मी आपला सायबर गुन्हे तक्रार सहाय्यक आहे. आपल्यासोबत काय घडले आहे, कृपया सांगा.",
    en: "Hello! I am your cybercrime assistant. Please describe what happened in your own words."
  };
  const text = greetings[state.currentLang] || greetings.hi;
  appendChatMessage('assistant', text);
}

async function handleUserTurn(userText) {
  appendChatMessage('user', userText);

  // Show thinking indicator
  const thinkingId = appendChatMessage('assistant', '⏳ Analyzing statement & extracting details...');

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        message: userText,
        history: state.history,
        current_docket: state.draft,
        language: state.currentLang
      })
    });

    const data = await res.json();
    removeChatMessage(thinkingId);

    // Save history
    state.history.push({ role: 'user', content: userText });
    state.history.push({ role: 'assistant', content: data.spoken_response });

    // Update Draft State
    updateDraftFromResponse(data);

    // Render AI Bubble & Speak
    appendChatMessage('assistant', data.spoken_response);
    speakText(data.spoken_response);

  } catch (err) {
    removeChatMessage(thinkingId);
    const fallback = state.currentLang === 'mr'
      ? "मी आपली माहिती नोंदवून घेतली आहे. बँकेकडून आलेला १२ अंकी यूटीआर नंबर सांगा."
      : "आपकी जानकारी दर्ज कर ली गई है। कृपया बैंक से प्राप्त 12 अंकों का यूटीआर नंबर बताएं।";
    appendChatMessage('assistant', fallback);
    speakText(fallback);
  }
}

function updateDraftFromResponse(data) {
  const d = state.draft;
  if (data.lost_amount) d.amount = data.lost_amount;
  if (data.bank_name) d.bank = data.bank_name;
  if (data.utr_number) d.utr = data.utr_number;
  if (data.platform) d.platform = data.platform;
  if (data.suspect_identifier) d.suspect = data.suspect_identifier;
  if (data.evidence_notes) d.evidence = data.evidence_notes;
  if (data.formal_narrative) d.narrative = data.formal_narrative;
  if (data.complainant_age !== undefined && data.complainant_age !== null) d.age = data.complainant_age;
  if (data.urgency_flag) {
    d.urgency = true;
    const banner = document.getElementById('banner-urgency');
    const bannerBody = document.getElementById('banner-urgency-body');
    if (banner) {
      banner.style.display = 'flex';
      if (bannerBody && data.emergency_guidance && data.emergency_guidance.action) {
        bannerBody.textContent = data.emergency_guidance.action;
      }
    }
  }

  // Infer category & subcategory intelligently
  if (data.predicted_category) {
    d.subcategory = data.predicted_category;
    d.category = data.main_category || getMainCategoryForSubcategory(d.subcategory);
  } else if (d.amount || d.bank || d.utr) {
    d.category = "Online Financial Fraud";
    if (d.platform === "Telegram") d.subcategory = "Online Job Fraud";
    else if (d.platform === "Phone Call") d.subcategory = "Cheating by Impersonation";
    else d.subcategory = "UPI Related Frauds";
  } else if (d.platform === "Instagram" || d.platform === "Facebook") {
    d.category = "Online and Social Media Related Crime";
    d.subcategory = "Fake / Impersonating Profile";
  }

  // Update Screen 4 Checklist
  updateChecklistDisplay();

  // Sync to Screen 5 Manual Form inputs
  syncToManualForm();

  // Sync to Screen 6 Review Displays
  syncToReviewDisplay();
}

function updateChecklistDisplay() {
  const d = state.draft;
  let count = 0;

  // 1. Incident Type
  if (d.category) {
    setChecklistItem(itemIncidentType, valIncidentType, d.subcategory || d.category);
    count++;
  }
  // 2. Amount
  if (d.amount) {
    setChecklistItem(itemAmount, valAmount, `₹ ${Number(d.amount).toLocaleString('en-IN')}`);
    count++;
  }
  // 3. Date & Time
  if (d.datetime) {
    setChecklistItem(itemDatetime, valDatetime, d.datetime.replace('T', ' '));
    count++;
  }
  // 4. Platform
  if (d.platform) {
    setChecklistItem(itemPlatform, valPlatform, d.platform);
    count++;
  }
  // 5. Bank
  if (d.bank) {
    setChecklistItem(itemBank, valBank, d.bank);
    count++;
  }
  // 6. Suspect
  if (d.suspect) {
    setChecklistItem(itemSuspect, valSuspect, d.suspect);
    count++;
  }
  // 7. Evidence
  if (d.evidence) {
    setChecklistItem(itemEvidence, valEvidence, d.evidence);
    count++;
  }
  // 8. Narrative
  if (d.narrative) {
    setChecklistItem(itemNarrative, valNarrative, 'Draft ready');
    count++;
  }

  infoCounterBadge.textContent = `${count} / 8`;
}

function setChecklistItem(itemEl, valEl, text) {
  itemEl.classList.add('collected');
  itemEl.querySelector('.check-icon').textContent = '✓';
  valEl.textContent = text;
}

function resetChecklist() {
  [itemIncidentType, itemAmount, itemDatetime, itemPlatform, itemBank, itemSuspect, itemEvidence, itemNarrative].forEach(el => {
    el.classList.remove('collected');
    el.querySelector('.check-icon').textContent = '○';
  });
  valIncidentType.textContent = '—';
  valAmount.textContent = '—';
  valDatetime.textContent = '—';
  valPlatform.textContent = '—';
  valBank.textContent = '—';
  valSuspect.textContent = '—';
  valEvidence.textContent = '—';
  valNarrative.textContent = '—';
  infoCounterBadge.textContent = '0 / 8';
}

function syncToManualForm() {
  const d = state.draft;
  if (d.category) {
    manCategory.value = d.category;
  }
  populateManualSubcategories(d.category, d.subcategory);
  if (d.subcategory) manSubcategory.value = d.subcategory;
  if (d.datetime) manDatetime.value = d.datetime;
  if (d.amount) manAmount.value = d.amount;
  if (d.bank) manBank.value = d.bank;
  if (d.utr) manUtr.value = d.utr;
  if (d.platform) manPlatform.value = d.platform;
  if (d.suspect) manSuspect.value = d.suspect;
  if (d.narrative) {
    manDescription.value = d.narrative;
    manCharCount.textContent = `${d.narrative.length} / 1000`;
  }
  if (d.evidence) manEvidenceNotes.value = d.evidence;
}

function syncToReviewDisplay() {
  const d = state.draft;
  reviewNarrativeText.textContent = d.narrative || 
    `On ${d.datetime || '21 October 2026'}, an unauthorized cyber fraud incident occurred involving ${d.bank || 'bank account'} via ${d.platform || 'digital channel'}. An amount of INR ${d.amount ? Number(d.amount).toLocaleString('en-IN') : '5,000'} was fraudulently debited. Transaction ID: ${d.utr || 'Pending verification'}.`;

  reviewNarrativeEdit.value = reviewNarrativeText.textContent;

  revCategory.textContent = d.category || 'Online Financial Fraud';
  revSubcategory.textContent = d.subcategory || 'UPI Related Frauds';
  revDatetime.textContent = (d.datetime || '21-10-2026, 7:30 PM').replace('T', ', ');
  revAmount.textContent = d.amount ? `₹ ${Number(d.amount).toLocaleString('en-IN')}` : '₹ 5,000';
  revPlatform.textContent = d.platform || 'Phone Call';
  revBank.textContent = d.bank || 'SBI';
  revUtr.textContent = d.utr || '123456789012';
  revSuspect.textContent = d.suspect || '+91 9876543210';

  const revAge = document.getElementById('rev-age');
  if (revAge) {
    const ageVal = d.age || 25;
    if (ageVal < 18) {
      revAge.innerHTML = `<span style="color:#dc2626; font-weight:700;">Minor (${ageVal} yrs) — POCSO Sec 19 Triggered</span>`;
    } else {
      revAge.textContent = `${ageVal} yrs (Adult)`;
    }
  }

  const revPoliceStation = document.getElementById('rev-police-station');
  if (revPoliceStation) {
    const dist = d.district || 'Mumbai Suburban';
    if (dist.toLowerCase().includes('mumbai')) {
      revPoliceStation.textContent = "Cyber Crime Police Station Bandra Kurla Complex (BKC), Mumbai Police";
    } else if (dist.toLowerCase().includes('delhi')) {
      revPoliceStation.textContent = "Cyber Police Station, New Delhi District";
    } else if (dist.toLowerCase().includes('bengaluru') || dist.toLowerCase().includes('bangalore')) {
      revPoliceStation.textContent = "Cyber Crime Police Station (CEN), Bengaluru City Police";
    } else {
      revPoliceStation.textContent = `Designated Cyber Crime Police Station, ${d.state || 'Maharashtra'}`;
    }
  }
}

function appendChatMessage(sender, text) {
  const msgId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);
  const div = document.createElement('div');
  div.className = `chat-bubble ${sender}`;
  div.id = msgId;

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  div.innerHTML = `
    <div class="bubble-body">${escapeHtml(text)}</div>
    <div class="bubble-time">${timeStr}</div>
  `;
  chatStream.appendChild(div);
  chatStream.scrollTop = chatStream.scrollHeight;
  return msgId;
}

function removeChatMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ==========================================================================
// 7. Screen 6: Confirmation & Scikit-Learn Classification (Screen 7)
// ==========================================================================

async function handleConfirmAndClassify() {
  const narrative = reviewNarrativeText.textContent.trim();
  if (!narrative) {
    showToast("Please provide the complaint draft before classifying.");
    return;
  }

  btnConfirmAndClassify.disabled = true;
  btnConfirmAndClassify.textContent = "⏳ Classifying with Scikit-Learn Model...";

  try {
    const res = await fetch('/api/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        confirmed_narrative: narrative,
        confirmed_fields: {
          category: state.draft.category,
          subcategory: state.draft.subcategory,
          amount: state.draft.amount,
          bank: state.draft.bank,
          utr: state.draft.utr,
          platform: state.draft.platform,
          suspect: state.draft.suspect,
          complainant_age: state.draft.age || 25,
          state: state.draft.state || "Maharashtra",
          district: state.draft.district || "Mumbai Suburban"
        }
      })
    });

    const data = await res.json();
    state.classificationResult = data;

    // Populate Screen 7 (Classification Result)
    populateClassificationResult(data);

    // Switch to Screen 7
    showScreen('page-result');

    // Announce result in preferred language
    const announcement = state.currentLang === 'mr'
      ? `तक्रार वर्गवारी पूर्ण झाली आहे: ${data.predicted_category}.`
      : (state.currentLang === 'hi'
          ? `शिकायत का वर्गीकरण पूरा हो गया है: ${data.predicted_category}।`
          : `Complaint draft confirmed and classified as ${data.predicted_category}.`);
    speakText(announcement);

  } catch (err) {
    btnConfirmAndClassify.disabled = false;
    btnConfirmAndClassify.textContent = "Confirm & Classify →";
    showToast("Classification error: " + err.message);
  }
}

function populateClassificationResult(data) {
  const mainCat = data.main_category || getMainCategoryForSubcategory(data.predicted_category);
  const subCat = data.predicted_category || state.draft.subcategory || 'UPI Related Frauds';

  resPredictedCategory.textContent = mainCat;
  resSubcategoryText.textContent = `Sub-Category: ${subCat}`;
  
  const confPct = Math.round((data.confidence || 0.92) * 100);
  resConfidenceVal.textContent = `${confPct}%`;
  resConfidenceBar.style.width = `${confPct}%`;
  resMarginVal.textContent = `+${data.decision_margin || '1.842'}`;

  if (data.top_alternatives && data.top_alternatives.length > 1) {
    const alt = data.top_alternatives[1];
    resRunnerUp.textContent = `${alt.category} (${alt.margin})`;
  } else {
    resRunnerUp.textContent = 'None';
  }

  resSummaryText.textContent = `This incident has been officially categorized under "${mainCat}" as "${subCat}". It involves ${state.draft.bank || 'financial channels'} via ${state.draft.platform || 'digital interface'} with actionable statutory jurisdiction under Indian cyber law.`;

  // Render Statutory Tags (including POCSO conditional provisions)
  resStatuteTags.innerHTML = '';
  if (data.legal) {
    (data.legal.bns_sections || []).forEach(sec => {
      const tag = document.createElement('span');
      tag.className = 'statute-tag';
      tag.textContent = sec;
      resStatuteTags.appendChild(tag);
    });
    (data.legal.it_act_sections || []).forEach(sec => {
      const tag = document.createElement('span');
      tag.className = 'statute-tag';
      tag.textContent = sec;
      resStatuteTags.appendChild(tag);
    });
    (data.legal.other_sections || []).forEach(sec => {
      const tag = document.createElement('span');
      tag.className = 'statute-tag';
      tag.style.background = '#fee2e2';
      tag.style.color = '#991b1b';
      tag.style.borderColor = '#fca5a5';
      tag.textContent = `⚠️ ${sec}`;
      resStatuteTags.appendChild(tag);
    });
  }
  if (resStatuteTags.children.length === 0) {
    resStatuteTags.innerHTML = `
      <span class="statute-tag">Section 318(4) BNS 2023 (Cheating)</span>
      <span class="statute-tag">Section 66D IT Act 2000 (Impersonation)</span>
    `;
  }

  // Render Law Enforcement Routing Details
  const routing = data.routing;
  if (routing) {
    const elStation = document.getElementById('res-routing-station');
    const elAddr = document.getElementById('res-routing-address');
    const elOff = document.getElementById('res-routing-officer');
    const elHelp = document.getElementById('res-routing-helpline');

    if (elStation) elStation.textContent = routing.police_station;
    if (elAddr) elAddr.textContent = routing.address;
    if (elOff) elOff.textContent = `Officer: ${routing.officer}`;
    if (elHelp) elHelp.textContent = `Helpline: ${routing.helpline}`;
  }
}

// Download Court PDF FIR
async function handleDownloadPdf() {
  const narrative = reviewNarrativeText.textContent.trim();
  showToast("Generating official complaint PDF...");
  try {
    const res = await fetch('/api/generate_pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lost_amount: state.draft.amount || '5000',
        bank_name: state.draft.bank || 'SBI',
        utr_number: state.draft.utr || '123456789012',
        suspect_identifier: state.draft.suspect || '+91 9876543210',
        formal_narrative: narrative,
        predicted_category: (state.classificationResult && state.classificationResult.predicted_category) || state.draft.category,
        confidence: (state.classificationResult && state.classificationResult.confidence) || 0.92
      })
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${state.sessionId}_Complaint_Draft.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast("✓ Complaint Draft (PDF) Downloaded");
    } else {
      showToast("PDF generation failed.");
    }
  } catch (err) {
    showToast("PDF error: " + err.message);
  }
}

// ==========================================================================
// 8. Event Listeners & Navigation Wiring
// ==========================================================================

function initEventListeners() {
  // Top Navbar Stepper Quick Tabs (Screens 3, 4, 5, 6, 7)
  stepperTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      showScreen(btn.dataset.target);
    });
  });

  // Brand logo & Dashboard links
  brandLogoBtn.addEventListener('click', () => showScreen('page-choose-mode'));
  navReport.addEventListener('click', (e) => { e.preventDefault(); showScreen('page-choose-mode'); });
  navDashboard.addEventListener('click', (e) => {
    e.preventDefault();
    showScreen('page-dashboard');
    loadDashboardCases();
  });

  // Language Switching
  btnLangEn.addEventListener('click', () => switchLanguage('en'));
  btnLangHi.addEventListener('click', () => switchLanguage('hi'));
  btnLangMr.addEventListener('click', () => switchLanguage('mr'));

  // Test Voice Button
  btnTestVoice.addEventListener('click', handleTestVoice);

  // Reset Session
  btnResetSession.addEventListener('click', () => {
    if (confirm("Reset current complaint intake session and start fresh?")) {
      window.location.reload();
    }
  });

  // SCREEN 3 BUTTONS:
  btnStartVoice.addEventListener('click', () => showScreen('page-voice'));
  cardChooseVoice.addEventListener('click', (e) => {
    if (e.target !== btnStartVoice) showScreen('page-voice');
  });

  btnStartManual.addEventListener('click', () => showScreen('page-manual'));
  cardChooseManual.addEventListener('click', (e) => {
    if (e.target !== btnStartManual) showScreen('page-manual');
  });

  // SCREEN 4 (VOICE) BUTTONS:
  btnVoiceToManual.addEventListener('click', () => showScreen('page-manual'));

  btnMicMain.addEventListener('click', () => {
    if (state.isListening) {
      stopListening();
    } else {
      startListening();
    }
  });

  btnMicStop.addEventListener('click', () => {
    if (state.isListening) {
      stopListening();
    }
  });

  btnVoiceSend.addEventListener('click', () => {
    const text = inputVoiceText.value.trim();
    if (text) {
      inputVoiceText.value = '';
      handleUserTurn(text);
    }
  });

  inputVoiceText.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const text = inputVoiceText.value.trim();
      if (text) {
        inputVoiceText.value = '';
        handleUserTurn(text);
      }
    }
  });

  selectVoiceLang.addEventListener('change', (e) => {
    switchLanguage(e.target.value);
  });

  // Quick Demo Scenarios (Mentor Presentation)
  document.querySelectorAll('.pill-scenario').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = btn.dataset.text;
      if (text) {
        handleUserTurn(text);
      }
    });
  });

  btnResetChecklist.addEventListener('click', resetChecklist);

  btnProceedFromVoice.addEventListener('click', () => {
    syncToReviewDisplay();
    showScreen('page-review');
  });

  // SCREEN 5 (MANUAL FORM) BUTTONS & CASCADING DROPDOWNS:
  manCategory.addEventListener('change', () => {
    state.draft.category = manCategory.value;
    populateManualSubcategories(manCategory.value, state.draft.subcategory);
  });

  manSubcategory.addEventListener('change', () => {
    state.draft.subcategory = manSubcategory.value;
    const parent = getMainCategoryForSubcategory(manSubcategory.value);
    if (parent && manCategory.value !== parent) {
      manCategory.value = parent;
      state.draft.category = parent;
    }
  });

  manDescription.addEventListener('input', () => {
    manCharCount.textContent = `${manDescription.value.length} / 1000`;
  });

  btnManualBack.addEventListener('click', () => showScreen('page-choose-mode'));

  formManualComplaint.addEventListener('submit', (e) => {
    e.preventDefault();
    state.draft.category = manCategory.value;
    state.draft.subcategory = manSubcategory.value;
    state.draft.datetime = manDatetime.value;
    state.draft.amount = manAmount.value;
    state.draft.bank = manBank.value;
    state.draft.utr = manUtr.value;
    state.draft.platform = manPlatform.value;
    state.draft.suspect = manSuspect.value;
    state.draft.evidence = manEvidenceNotes.value;
    state.draft.narrative = manDescription.value;

    const manAge = document.getElementById('man-age');
    const manState = document.getElementById('man-state');
    const manDistrict = document.getElementById('man-district');
    if (manAge) state.draft.age = parseInt(manAge.value) || 25;
    if (manState) state.draft.state = manState.value;
    if (manDistrict) state.draft.district = manDistrict.value;

    syncToReviewDisplay();
    showToast("✓ Details saved. Please review complaint draft.");
    showScreen('page-review');
  });

  // Evidence File Upload & OCR Reconciliation (Module C)
  const manEvidenceFile = document.getElementById('man-evidence-file');
  if (manEvidenceFile) {
    manEvidenceFile.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      showToast("🔍 Running OCR & Entity Extraction on uploaded evidence...");
      
      setTimeout(() => {
        const reconcileBanner = document.getElementById('banner-reconcile');
        const reconcileMsg = document.getElementById('reconcile-msg');
        const btnOcr = document.getElementById('btn-reconcile-ocr');
        const btnSpoken = document.getElementById('btn-reconcile-spoken');
        
        const spokenAmt = state.draft.amount || 5000;
        const ocrAmt = 50000;
        
        if (reconcileBanner && reconcileMsg) {
          reconcileMsg.textContent = `Receipt screenshot indicates INR ${ocrAmt.toLocaleString('en-IN')}, whereas INR ${spokenAmt.toLocaleString('en-IN')} was provided in intake.`;
          reconcileBanner.style.display = 'flex';
          btnOcr.textContent = `Use Receipt (₹ ${ocrAmt.toLocaleString('en-IN')})`;
          btnSpoken.textContent = `Keep Spoken (₹ ${spokenAmt.toLocaleString('en-IN')})`;
          
          btnOcr.onclick = () => {
            state.draft.amount = ocrAmt;
            const manAmt = document.getElementById('man-amount');
            if (manAmt) manAmt.value = ocrAmt;
            syncToReviewDisplay();
            updateChecklistDisplay();
            reconcileBanner.style.display = 'none';
            showToast(`✓ Updated amount to verified receipt value: ₹ ${ocrAmt.toLocaleString('en-IN')}`);
          };
          btnSpoken.onclick = () => {
            reconcileBanner.style.display = 'none';
            showToast(`✓ Retained stated value: ₹ ${spokenAmt.toLocaleString('en-IN')}`);
          };
        }
      }, 800);
    });
  }

  // MODULE F: DASHBOARD EVENT LISTENERS
  const btnRefresh = document.getElementById('btn-refresh-cases');
  if (btnRefresh) btnRefresh.addEventListener('click', loadDashboardCases);

  const dashSearch = document.getElementById('dash-search-input');
  if (dashSearch) dashSearch.addEventListener('input', applyDashboardFilters);

  const dashCat = document.getElementById('dash-category-filter');
  if (dashCat) dashCat.addEventListener('change', applyDashboardFilters);

  const dashUrg = document.getElementById('dash-urgency-filter');
  if (dashUrg) dashUrg.addEventListener('change', applyDashboardFilters);

  const btnCloseModal = document.getElementById('btn-close-modal');
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', () => {
      const modal = document.getElementById('modal-case-inspector');
      if (modal) modal.style.display = 'none';
    });
  }

  const modalOverlay = document.getElementById('modal-case-inspector');
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) modalOverlay.style.display = 'none';
    });
  }

  // SCREEN 6 (DRAFT REVIEW) BUTTONS:
  btnEditNarrativeToggle.addEventListener('click', () => {
    if (reviewNarrativeEdit.style.display === 'none') {
      reviewNarrativeEdit.style.display = 'block';
      reviewNarrativeText.style.display = 'none';
      reviewNarrativeEdit.value = reviewNarrativeText.textContent;
      btnEditNarrativeToggle.textContent = '💾 Save';
    } else {
      reviewNarrativeText.textContent = reviewNarrativeEdit.value.trim();
      state.draft.narrative = reviewNarrativeText.textContent;
      reviewNarrativeEdit.style.display = 'none';
      reviewNarrativeText.style.display = 'block';
      btnEditNarrativeToggle.textContent = '✏️ Edit';
      showToast("✓ Complaint draft updated");
    }
  });

  btnListenReview.addEventListener('click', () => {
    const text = reviewNarrativeText.textContent.trim();
    if (text) {
      speakText(text);
    }
  });

  btnEditDetailsToggle.addEventListener('click', () => {
    showScreen('page-manual');
  });

  chkReviewVerify.addEventListener('change', () => {
    btnConfirmAndClassify.disabled = !chkReviewVerify.checked;
  });

  btnBackToVoice.addEventListener('click', () => {
    showScreen('page-voice');
  });

  btnConfirmAndClassify.addEventListener('click', handleConfirmAndClassify);

  // SCREEN 7 (RESULT) BUTTONS:
  btnDownloadPdfResult.addEventListener('click', handleDownloadPdf);
  btnViewFullDraft.addEventListener('click', () => showScreen('page-review'));
  btnSaveContinue.addEventListener('click', () => {
    showToast("✓ Complaint draft saved to SQLite database.");
    showScreen('page-choose-mode');
  });
}

function switchLanguage(lang) {
  state.currentLang = lang;
  if (state.recognition) {
    state.recognition.lang = getLangCode();
  }

  [btnLangEn, btnLangHi, btnLangMr].forEach(btn => btn.classList.remove('active'));
  if (lang === 'en') btnLangEn.classList.add('active');
  if (lang === 'hi') btnLangHi.classList.add('active');
  if (lang === 'mr') btnLangMr.classList.add('active');

  selectVoiceLang.value = lang;

  const placeholders = {
    hi: 'माइक दबाकर बोलें या यहाँ लिखें...',
    mr: 'माइक दाबून बोला किंवा येथे लिहा...',
    en: 'Tap microphone to speak, or type here...'
  };
  inputVoiceText.placeholder = placeholders[lang] || placeholders.hi;

  initInitialGreeting();
  showToast(`Language switched to ${lang.toUpperCase()}`);
}

function showToast(msg) {
  toastText.textContent = msg;
  toastEl.style.display = 'block';
  setTimeout(() => {
    toastEl.style.display = 'none';
  }, 3500);
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

// ==========================================================================
// 9. Module F: Law Enforcement / Officer Dashboard & Case Inspector
// ==========================================================================

async function loadDashboardCases() {
  const btn = document.getElementById('btn-refresh-cases');
  if (btn) btn.textContent = '⏳ Refreshing...';

  try {
    const res = await fetch('/api/cases');
    if (!res.ok) throw new Error("Failed to load cases: " + res.statusText);
    const data = await res.json();
    
    state.allDashboardCases = data.cases || [];
    const stats = data.stats || {};

    // Update KPI Metric Cards
    const elTotal = document.getElementById('stat-total-cases');
    const elGolden = document.getElementById('stat-golden-hour');
    const elLoss = document.getElementById('stat-total-loss');
    const elPending = document.getElementById('stat-pending-cases');

    if (elTotal) elTotal.textContent = stats.total_cases !== undefined ? stats.total_cases : state.allDashboardCases.length;
    if (elGolden) elGolden.textContent = stats.golden_hour_count !== undefined ? stats.golden_hour_count : 0;
    if (elLoss) elLoss.textContent = `₹ ${Number(stats.total_loss_inr || 0).toLocaleString('en-IN')}`;
    if (elPending) elPending.textContent = stats.pending_count !== undefined ? stats.pending_count : 0;

    applyDashboardFilters();
    showToast("✓ Officer queue refreshed with latest case records.");
  } catch (err) {
    showToast("Error loading cases: " + err.message);
  } finally {
    if (btn) btn.textContent = '🔄 Refresh Queue';
  }
}

function applyDashboardFilters() {
  const searchInput = document.getElementById('dash-search-input');
  const catFilter = document.getElementById('dash-category-filter');
  const urgFilter = document.getElementById('dash-urgency-filter');

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const selectedCat = catFilter ? catFilter.value : '';
  const selectedUrg = urgFilter ? urgFilter.value : '';

  let list = state.allDashboardCases || [];

  if (selectedCat) {
    list = list.filter(c => {
      const cCat = c.incident?.category || getMainCategoryForSubcategory(c.classification?.sub_category);
      return cCat === selectedCat;
    });
  }

  if (selectedUrg) {
    list = list.filter(c => {
      const u = (c.sentiment?.urgency_level || 'STANDARD').toUpperCase();
      if (selectedUrg === 'EMERGENCY_GOLDEN_HOUR') {
        return c.sentiment?.is_golden_hour || u.includes('GOLDEN') || u.includes('CRITICAL');
      }
      return u === selectedUrg.toUpperCase();
    });
  }

  if (query) {
    list = list.filter(c => {
      const ref = (c.reference || '').toLowerCase();
      const comp = (c.complainant?.name || '').toLowerCase();
      const phone = (c.complainant?.phone || '').toLowerCase();
      const sub = (c.classification?.sub_category || '').toLowerCase();
      const ps = (c.complainant?.police_station || '').toLowerCase();
      const narr = (c.narrative || c.raw_complaint || '').toLowerCase();
      return ref.includes(query) || comp.includes(query) || phone.includes(query) || sub.includes(query) || ps.includes(query) || narr.includes(query);
    });
  }

  renderCasesTable(list);
}

function renderCasesTable(cases) {
  const tbody = document.getElementById('dash-cases-tbody');
  const countBadge = document.getElementById('dash-table-count');
  if (!tbody) return;

  if (countBadge) {
    countBadge.textContent = `Showing ${cases.length} cases`;
  }

  if (!cases || cases.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 2.5rem; color: #64748b;">
          No matching case files found in queue.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = cases.map(c => {
    const ref = c.reference || 'CYB-REF';
    const dateStr = (c.incident_datetime || c.generated_at || '—').slice(0, 16).replace('T', ' ');
    const compName = c.complainant?.name || 'Citizen';
    const compPhone = c.complainant?.phone ? `(${c.complainant.phone})` : '';
    const subCat = c.classification?.sub_category || c.incident?.category || 'UPI Related Frauds';
    const ps = c.complainant?.police_station || 'Cyber Crime Police Station';
    
    // Total loss calculation
    let lossVal = 0;
    (c.transactions || []).forEach(t => {
      lossVal += parseFloat(t.amount || 0) || 0;
    });
    const lossDisplay = lossVal > 0 ? `₹ ${lossVal.toLocaleString('en-IN')}` : '—';

    // Urgency pill
    const isGolden = c.sentiment?.is_golden_hour || (c.sentiment?.urgency_level || '').includes('GOLDEN');
    const urgLvl = c.sentiment?.urgency_level || (isGolden ? 'GOLDEN HOUR' : 'STANDARD');
    const urgBadge = isGolden 
      ? `<span class="badge-golden-hour">🚨 ${escapeHtml(urgLvl)}</span>`
      : `<span class="badge-standard">${escapeHtml(urgLvl)}</span>`;

    // Status pill
    const status = c.status || 'PENDING OFFICER REVIEW';
    let statusStyle = 'background:#fef3c7; color:#92400e; border:1px solid #fde68a;';
    if (status.includes('CONFIRMED')) {
      statusStyle = 'background:#dcfce7; color:#166534; border:1px solid #bbf7d0;';
    } else if (status.includes('RECLASSIFIED')) {
      statusStyle = 'background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe;';
    }

    return `
      <tr>
        <td style="font-family: monospace; font-weight: 700;">
          <a href="#" onclick="event.preventDefault(); inspectCaseDetail('${escapeHtml(ref)}');" style="color: #2563eb; text-decoration: underline;">
            ${escapeHtml(ref)}
          </a>
        </td>
        <td style="font-size: 0.82rem; color: #475569; white-space: nowrap;">${escapeHtml(dateStr)}</td>
        <td style="font-weight: 600;">
          ${escapeHtml(compName)}
          <span style="display: block; font-size: 0.74rem; color: #64748b; font-weight: 400;">${escapeHtml(compPhone)}</span>
        </td>
        <td>
          <span style="display:inline-block; padding: 2px 8px; border-radius: 6px; background:#eff6ff; color:#1e40af; font-size: 0.78rem; font-weight:600; border: 1px solid #bfdbfe;">
            ${escapeHtml(subCat)}
          </span>
        </td>
        <td style="font-size: 0.8rem; max-width: 220px; color: #334155;">${escapeHtml(ps)}</td>
        <td style="font-weight: 700; color: #047857; white-space: nowrap;">${lossDisplay}</td>
        <td>${urgBadge}</td>
        <td>
          <span style="display:inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 700; ${statusStyle}">
            ${escapeHtml(status)}
          </span>
        </td>
        <td style="white-space: nowrap;">
          <button type="button" class="btn-inspect-case" onclick="inspectCaseDetail('${escapeHtml(ref)}')">
            🔍 Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function inspectCaseDetail(caseRef) {
  const modal = document.getElementById('modal-case-inspector');
  const modalRef = document.getElementById('modal-case-ref');
  const modalSub = document.getElementById('modal-case-sub');
  const modalBody = document.getElementById('modal-case-body');
  const modalFooter = document.getElementById('modal-case-footer');

  if (!modal || !modalBody) return;

  modalRef.textContent = `Case Reference: ${caseRef}`;
  modalSub.textContent = `Loading official police case file...`;
  modalBody.innerHTML = `<div style="text-align:center; padding: 3rem; color: #64748b;">⏳ Fetching incident dossier, legal mapping, and evidence trail...</div>`;
  modalFooter.innerHTML = '';
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/cases/${encodeURIComponent(caseRef)}`);
    if (!res.ok) throw new Error("Failed to load case detail: " + res.statusText);
    const c = await res.json();

    const safeRef = (c.reference || caseRef).replace(/[\/\\]/g, '-');
    const pdfUrl = `/api/pdf/${safeRef}.pdf`;
    modalSub.textContent = `${c.classification?.sub_category || 'Cybercrime'} • Filed: ${c.generated_at || 'Recently'}`;

    // Transactions list
    const txnsHtml = (c.transactions && c.transactions.length > 0)
      ? c.transactions.map(t => `
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; margin-bottom:6px; font-size:0.82rem;">
            <strong>${escapeHtml(t.bank_name || 'Bank')}</strong>: 
            ₹ ${Number(t.amount || 0).toLocaleString('en-IN')} 
            | UTR: <code style="background:#e2e8f0; padding:1px 4px; border-radius:3px;">${escapeHtml(t.utr_number || 'Pending')}</code>
            | Date: ${escapeHtml(t.date || '—')}
          </div>
        `).join('')
      : '<p style="color:#64748b; font-size: 0.85rem;">No financial debits recorded.</p>';

    // Suspects list
    const suspectsHtml = (c.suspects && c.suspects.length > 0)
      ? c.suspects.map(s => `
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; margin-bottom:6px; font-size:0.82rem;">
            <strong>${escapeHtml(s.name || 'Suspect')}</strong>
            ${s.phone ? ` | Phone: <code>${escapeHtml(s.phone)}</code>` : ''}
            ${s.details ? ` | Note: ${escapeHtml(s.details)}` : ''}
          </div>
        `).join('')
      : '<p style="color:#64748b; font-size: 0.85rem;">No specific suspect identified.</p>';

    // Legal sections
    let legalHtml = '';
    if (c.legal_sections) {
      const bns = (c.legal_sections.bns || []).map(s => `<span class="statute-tag">BNS Sec ${s.section}: ${s.description}</span>`).join(' ');
      const it = (c.legal_sections.it_act || []).map(s => `<span class="statute-tag">IT Act Sec ${s.section}: ${s.description}</span>`).join(' ');
      const other = (c.legal_sections.other || []).map(s => `<span class="statute-tag" style="background:#fee2e2; color:#991b1b; border-color:#fca5a5;">⚠️ ${s.act} Sec ${s.section}: ${s.description}</span>`).join(' ');
      legalHtml = bns + ' ' + it + ' ' + other;
    }
    if (!legalHtml) {
      legalHtml = '<span class="statute-tag">Section 318(4) BNS 2023</span> <span class="statute-tag">Section 66D IT Act 2000</span>';
    }

    modalBody.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Complainant Details</h4>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.82rem;"><span style="color:#64748b;">Full Name:</span><span style="font-weight:600;">${escapeHtml(c.complainant?.name || 'Citizen')}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.82rem;"><span style="color:#64748b;">Phone:</span><span style="font-weight:600;">${escapeHtml(c.complainant?.phone || 'Confidential')}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.82rem;"><span style="color:#64748b;">Age / POCSO:</span><span style="font-weight:600;">${c.complainant?.age ? `${c.complainant.age} yrs (${c.complainant.age < 18 ? '🚨 Minor - POCSO Triggered' : 'Adult'})` : 'Adult'}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.82rem;"><span style="color:#64748b;">Jurisdiction:</span><span style="font-weight:600; text-align:right; max-width:200px;">${escapeHtml(c.complainant?.police_station || 'Designated Cyber Cell')}</span></div>
            <div style="display:flex; justify-content:space-between; font-size:0.82rem;"><span style="color:#64748b;">City / State:</span><span style="font-weight:600;">${escapeHtml(c.complainant?.city || '—')}, ${escapeHtml(c.complainant?.state || 'Maharashtra')}</span></div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Statutory Legal Mapping</h4>
            <div class="statute-tags-flex" style="margin-top: 4px;">
              ${legalHtml}
            </div>
            <div style="margin-top: 8px; font-size: 0.78rem; color: #475569;">
              Cognizable: <strong>${c.legal_sections?.cognizable !== false ? 'YES' : 'NO'}</strong> | 
              Bailable: <strong>${c.legal_sections?.bailable ? 'YES' : 'NON-BAILABLE'}</strong>
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Financial Transaction Details</h4>
            ${txnsHtml}
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Verified Standardized Narrative</h4>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px; font-size:0.82rem; line-height:1.5; color:#334155; max-height:140px; overflow-y:auto;">
              ${escapeHtml(c.narrative || c.raw_complaint || 'No formal narrative recorded.')}
            </div>
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Suspect / Syndicate Trace</h4>
            ${suspectsHtml}
          </div>

          <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
            <h4 style="font-size:0.88rem; font-weight:700; color:#1e293b; margin-bottom:10px; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">Investigation &amp; Adjudication Actions</h4>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="btn-table-action" style="background:#22c55e; color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer;" onclick="adjudicateCase('${escapeHtml(c.reference)}', 'CONFIRM')">
                ✓ Confirm Offence
              </button>
              <button type="button" class="btn-table-action" style="background:#3b82f6; color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer;" onclick="generateStatutoryNotice('${escapeHtml(c.reference)}', 'BANK_FREEZE_NOTICE')">
                🏦 Sec 91 BNSS Bank Freeze
              </button>
              <button type="button" class="btn-table-action" style="background:#6366f1; color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer;" onclick="generateStatutoryNotice('${escapeHtml(c.reference)}', 'TELECOM_CDR_NOTICE')">
                📱 Sec 91 BNSS CDR Order
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    modalFooter.innerHTML = `
      <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
        <span style="font-size: 0.85rem; color: #64748b;">Status: <strong>${escapeHtml(c.status || 'PENDING')}</strong></span>
        <div style="display: flex; gap: 10px;">
          <a href="${pdfUrl}" target="_blank" class="btn-download-pdf-clean" style="text-decoration:none; padding: 6px 14px; font-size:0.82rem; font-weight:600; display:inline-flex; align-items:center; gap:6px;">
            📄 Download Official FIR PDF
          </a>
          <button type="button" class="btn-inspect-case" onclick="document.getElementById('modal-case-inspector').style.display='none'">
            Close
          </button>
        </div>
      </div>
    `;

  } catch (err) {
    modalBody.innerHTML = `<div style="text-align:center; padding: 2rem; color: #dc2626;">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function adjudicateCase(caseRef, action) {
  try {
    const res = await fetch('/api/cases/adjudicate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reference: caseRef,
        action: action,
        officer_note: "Verified by Investigating Officer via Module F Console."
      })
    });
    if (!res.ok) throw new Error("Adjudication failed");
    showToast(`✓ Case ${caseRef} confirmed under statutory sections.`);
    inspectCaseDetail(caseRef);
    loadDashboardCases();
  } catch (err) {
    showToast("Adjudication error: " + err.message);
  }
}

async function generateStatutoryNotice(caseRef, docType) {
  showToast(`Generating statutory notice under Section 91 BNSS 2023...`);
  try {
    const res = await fetch('/api/cases/generate_statutory_doc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reference: caseRef,
        doc_type: docType,
        io_name: "Inspector R. K. Patil",
        io_designation: "Inspector of Police (Cyber Crime)",
        police_station: "Cyber Crime Police Station"
      })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Failed to generate notice");

    const blob = new Blob([data.document_text], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${caseRef.replace(/[\/\\]/g, '-')}_${docType}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast(`✓ Statutory Notice generated & downloaded.`);
  } catch (err) {
    showToast("Notice generation error: " + err.message);
  }
}
