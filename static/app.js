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
  currentLang: 'en', // English is the default after a page reload.
  currentScreen: 'page-choose-mode',
  isListening: false,
  recognition: null,
  voices: [],
  history: [],
  counselorDocket: {},
  isSubmittingChat: false,
  evidenceFiles: [],
  ocrEntities: {},
  ocrDateTimeValues: { date: '', time: '' },
  evidenceReview: null,
  savedCaseReference: null,
  draft: {
    category: '',
    subcategory: '',
    datetime: '',
    amount: null,
    bank: '',
    utr: '',
    platform: '',
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
const navTrack = document.getElementById('nav-track');
const navInvestigatorOperations = document.getElementById('nav-investigator-operations');
const navInvestigatorImport = document.getElementById('nav-investigator-import');
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
const chkLocalConsent = document.getElementById('chk-local-consent');
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
  syncToReviewDisplay();

  // Show Initial Screen (Screen 3: Choose Mode)
  showScreen('page-choose-mode');

  // Load initial greeting into voice chat
  initInitialGreeting();
});

// Screen Router
function showScreen(screenId, scrollToTop = true) {
  state.currentScreen = screenId;
  const isDashboard = screenId === 'page-dashboard';
  const flowScreens = ['page-voice', 'page-manual', 'page-review', 'page-result'];
  const progress = document.getElementById('complaint-progress');
  const progressStage = screenId === 'page-result' ? 2 : screenId === 'page-review' ? 1 : 0;
  if (progress) {
    progress.hidden = !flowScreens.includes(screenId);
    progress.querySelectorAll('[data-progress-step]').forEach(step => {
      const index = Number(step.dataset.progressStep);
      step.classList.toggle('active', index === progressStage);
      step.classList.toggle('complete', index < progressStage);
    });
    progress.querySelectorAll('.progress-track').forEach((track, index) => {
      track.classList.toggle('complete', index < progressStage);
    });
  }
  document.body.classList.toggle('dashboard-mode', isDashboard);
  document.body.classList.toggle('intake-mode', flowScreens.includes(screenId));
  document.getElementById('top-nav-home')?.classList.toggle('active', screenId === 'page-choose-mode');
  document.getElementById('top-nav-prepare')?.classList.toggle('active', flowScreens.includes(screenId));
  document.getElementById('top-nav-track')?.classList.toggle('active', screenId === 'page-track');
  navDashboard.classList.toggle('active', isDashboard);
  navTrack?.classList.toggle('active', screenId === 'page-track');
  navReport.classList.toggle('active', !isDashboard && screenId !== 'page-track');
  navInvestigatorOperations?.classList.remove('active');
  navInvestigatorImport?.classList.remove('active');
  const reportLabel = document.getElementById('nav-report-label');
  if (reportLabel) reportLabel.textContent = isDashboard ? 'Public complaint intake' : 'Prepare a complaint';
  const dashboardLabel = document.getElementById('nav-dashboard-label');
  if (dashboardLabel) dashboardLabel.textContent = isDashboard ? 'Review queue' : 'Case review';
  const sideNav = document.getElementById('primary-side-nav');
  sideNav?.setAttribute('aria-label', isDashboard ? 'Investigator workspace navigation' : 'Complaint preparation navigation');

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

  if (scrollToTop) window.scrollTo({ top: 0, behavior: 'smooth' });
}

function startNewComplaintIfPreviousWasSaved() {
  if (!state.savedCaseReference) return;

  // Keep the previous server-side session and case intact, but make the next
  // complainant start with a new session and no prior transcript/OCR data.
  state.sessionId = 'CYB-2026-' + Math.floor(100000 + Math.random() * 900000);
  state.history = [];
  state.counselorDocket = {};
  state.evidenceFiles = [];
  state.ocrEntities = {};
  state.ocrDateTimeValues = { date: '', time: '' };
  state.evidenceReview = null;
  state.savedCaseReference = null;
  state.classificationResult = null;
  state.intakeAnalysis = null;
  state.draft = {
    category: '', subcategory: '', datetime: '', amount: null,
    bank: '', utr: '', platform: '', suspect: '', evidence: '',
    narrative: '', name: '', phone: '', email: '', age: null,
    state: '', district: '', city: '', address: '', relationship: 'Self'
  };

  if (lblSessionId) lblSessionId.textContent = state.sessionId;
  if (chatStream) chatStream.replaceChildren();
  if (inputVoiceText) inputVoiceText.value = '';
  if (manFileUpload) manFileUpload.value = '';
  const voiceEvidenceUpload = document.getElementById('voice-evidence-upload');
  const voiceNoteUpload = document.getElementById('voice-note-upload');
  if (voiceEvidenceUpload) voiceEvidenceUpload.value = '';
  if (voiceNoteUpload) voiceNoteUpload.value = '';
  ['man-category', 'man-datetime', 'man-amount', 'man-bank', 'man-utr', 'man-platform',
    'man-suspect', 'man-evidence-notes', 'man-description', 'man-name', 'man-phone',
    'man-email', 'man-age', 'man-state', 'man-district', 'man-city', 'man-address',
    'review-name', 'review-phone', 'review-email'].forEach(id => {
    const element = document.getElementById(id);
    if (element) element.value = '';
  });
  const reviewNarrativeText = document.getElementById('review-narrative-text');
  const reviewNarrativeEdit = document.getElementById('review-narrative-edit');
  const reviewVerify = document.getElementById('chk-review-verify');
  const localConsent = document.getElementById('chk-local-consent');
  const savedReference = document.getElementById('saved-case-reference');
  const voiceEvidencePanel = document.getElementById('voice-evidence-panel');
  const voiceEvidenceStatus = document.getElementById('voice-evidence-ocr-status');
  const voiceNoteStatus = document.getElementById('voice-note-status');
  if (reviewNarrativeText) reviewNarrativeText.textContent = '';
  if (reviewNarrativeEdit) reviewNarrativeEdit.value = '';
  if (reviewVerify) reviewVerify.checked = false;
  if (localConsent) localConsent.checked = false;
  if (btnConfirmAndClassify) {
    btnConfirmAndClassify.disabled = true;
    btnConfirmAndClassify.textContent = 'Confirm & Classify →';
  }
  if (btnSaveContinue) {
    btnSaveContinue.disabled = true;
    btnSaveContinue.textContent = 'Save and Continue →';
  }
  if (savedReference) savedReference.hidden = true;
  if (voiceEvidencePanel) voiceEvidencePanel.hidden = true;
  voiceEvidenceStatus?.replaceChildren();
  document.getElementById('evidence-ocr-status')?.replaceChildren();
  const reconcileBanner = document.getElementById('banner-reconcile');
  const urgencyBanner = document.getElementById('banner-urgency');
  if (reconcileBanner) reconcileBanner.style.display = 'none';
  if (urgencyBanner) urgencyBanner.style.display = 'none';
  if (voiceNoteStatus) voiceNoteStatus.textContent = '';
  document.getElementById('additional-transaction-rows')?.replaceChildren();
  document.getElementById('recipient-transaction-rows')?.replaceChildren();
  resetChecklist();
  populateManualSubcategories('', '');
  syncToReviewDisplay();
  initInitialGreeting();
}

// ==========================================================================
// 4. Dual-Engine Speech Recognition (Web Speech API + Local Whisper Fallback)
// ==========================================================================

let mediaRecorder = null;
let audioChunks = [];
let recognitionRestartTimer = null;
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
    // Browsers may end a speech-recognition session after a pause even while
    // the user is still speaking. Keep the explicit recording session active
    // and restart recognition until the user presses Stop.
    if (state.isListening) {
      clearTimeout(recognitionRestartTimer);
      recognitionRestartTimer = setTimeout(() => {
        if (!state.isListening) return;
        try {
          state.recognition.start();
        } catch (e) {
          // MediaRecorder continues to capture audio if recognition cannot restart.
        }
      }, 300);
    }
  };
}

async function startListening() {
  accumulatedWebSpeechText = '';
  audioChunks = [];

  state.isListening = true;
  btnMicStop.hidden = false;
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
      if (!state.isListening) {
        stream.getTracks().forEach(t => t.stop());
        return;
      }
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
  if (!state.isListening) return;
  if (state.recognition) {
    try {
      state.recognition.lang = getLangCode();
      state.recognition.start();
    } catch (e) {}
  }

}

function stopListening() {
  clearTimeout(recognitionRestartTimer);
  state.isListening = false;
  btnMicStop.hidden = true;
  btnMicMain.classList.remove('active-listening');
  btnMicLabel.textContent = 'Tap to Speak';
  statusDot.className = 'status-indicator-dot ready';
  statusText.textContent = 'Ready to help';

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
  if (state.isSubmittingChat || !String(userText || '').trim()) return;
  state.isSubmittingChat = true;
  appendChatMessage('user', userText);
  const sendButton = document.getElementById('btn-voice-send');
  if (sendButton) sendButton.disabled = true;
  if (btnMicMain) btnMicMain.disabled = true;
  if (inputVoiceText) inputVoiceText.disabled = true;

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
        current_docket: {
          ...state.counselorDocket,
          incident_category: state.counselorDocket.incident_category || state.draft.category,
          financial_loss_amount: state.counselorDocket.financial_loss_amount ?? state.draft.amount,
          bank_name: state.counselorDocket.bank_name || state.draft.bank,
          utr_number: state.counselorDocket.utr_number || state.draft.utr,
          platform_involved: state.counselorDocket.platform_involved || state.draft.platform,
          suspect_details: state.counselorDocket.suspect_details || state.draft.suspect,
          complainant_age: state.counselorDocket.complainant_age ?? state.draft.age
        },
        language: state.currentLang
      })
    });

    const data = await res.json();
    if (!res.ok || !data.spoken_response) throw new Error(data.detail || data.error || `The intake service returned ${res.status}.`);
    removeChatMessage(thinkingId);

    // Save history
    state.history.push({ role: 'user', content: userText });
    state.history.push({ role: 'assistant', content: data.spoken_response });
    if (state.evidenceFiles.length) await reconcileUploadedEvidence();

    // Update Draft State
    state.counselorDocket = { ...state.counselorDocket, ...data };
    updateDraftFromResponse(data);

    // Render AI Bubble & Speak
    appendChatMessage('assistant', data.spoken_response);
    speakText(data.spoken_response);

  } catch (err) {
    removeChatMessage(thinkingId);
    const fallback = state.currentLang === 'mr'
      ? 'तुमचे उत्तर जतन करता आले नाही. कृपया पुन्हा पाठवा; मी पुढचा प्रश्न अंदाजाने विचारणार नाही.'
      : state.currentLang === 'hi'
        ? 'आपका उत्तर अभी दर्ज नहीं हो सका। कृपया फिर से भेजें; मैं अगला सवाल अनुमान से नहीं पूछूँगा।'
        : 'I could not save that answer just now. Please send it again; I will not guess the next question.';
    appendChatMessage('assistant', fallback);
    speakText(fallback);
  } finally {
    state.isSubmittingChat = false;
    if (sendButton) sendButton.disabled = false;
    if (btnMicMain) btnMicMain.disabled = false;
    if (inputVoiceText) inputVoiceText.disabled = false;
  }
}

function updateDraftFromResponse(data) {
  const d = state.draft;
  if (data.lost_amount !== undefined && data.lost_amount !== null) d.amount = data.lost_amount;
  if (data.bank_name !== undefined && data.bank_name !== null) d.bank = data.bank_name;
  if (data.utr_number !== undefined && data.utr_number !== null) d.utr = data.utr_number;
  if (data.platform_involved || data.platform) d.platform = data.platform_involved || data.platform;
  if (data.suspect_details || data.suspect_identifier) d.suspect = data.suspect_details || data.suspect_identifier;
  if (data.evidence_available !== undefined && data.evidence_available !== null) d.evidence = data.evidence_available ? 'Evidence available' : 'No evidence';
  if (data.date_time_of_incident) d.datetime = data.date_time_of_incident;
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
  } else if (data.incident_category) {
    d.category = data.incident_category;
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
  updateVoiceEvidencePrompt(data.pending_field);
}

function updateVoiceEvidencePrompt(pendingField = state.counselorDocket.pending_field) {
  const panel = document.getElementById('voice-evidence-panel');
  if (!panel) return;
  const needsEvidence = ['utr', 'evidence', 'bank', 'amount', 'incident_time'].includes(pendingField)
    || (state.counselorDocket.evidence_available === true && state.evidenceFiles.length === 0);
  panel.hidden = !needsEvidence;
  panel.classList.toggle('voice-evidence-urgent', pendingField === 'utr' || pendingField === 'evidence');
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
  if (d.amount !== null && d.amount !== undefined && d.amount !== '') {
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

function normalizeDateTimeLocal(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})(?:T|\s+(\d{1,2}):(\d{2}))?/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}T${String(iso[4] || '00').padStart(2, '0')}:${iso[5] || '00'}`;
  const monthNames = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  let day, month, year;
  const numericDate = raw.match(/\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b/);
  const namedDate = raw.match(/\b(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{2,4})\b/);
  if (numericDate) { day = Number(numericDate[1]); month = Number(numericDate[2]); year = Number(numericDate[3]); }
  else if (namedDate) { day = Number(namedDate[1]); month = monthNames[namedDate[2].slice(0, 3).toLowerCase()]; year = Number(namedDate[3]); }
  if (!day || !month || !year) return '';
  if (year < 100) year += 2000;
  const time = raw.match(/\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?\b/i);
  let hour = Number(time?.[1] || 0), minute = Number(time?.[2] || 0);
  if (time?.[3]?.toUpperCase() === 'PM' && hour < 12) hour += 12;
  if (time?.[3]?.toUpperCase() === 'AM' && hour === 12) hour = 0;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day || hour > 23 || minute > 59) return '';
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

function syncToManualForm() {
  const d = state.draft;
  if (d.category) {
    manCategory.value = d.category;
  }
  populateManualSubcategories(d.category, d.subcategory);
  if (d.subcategory) manSubcategory.value = d.subcategory;
  if (d.datetime) manDatetime.value = normalizeDateTimeLocal(d.datetime) || d.datetime;
  if (d.amount !== null && d.amount !== undefined && d.amount !== '') manAmount.value = d.amount;
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
  const setValue = (id, value) => { const el = document.getElementById(id); if (el && value && !el.value) el.value = value; };
  setValue('review-name', d.name); setValue('review-phone', d.phone); setValue('review-email', d.email);
  reviewNarrativeText.textContent = d.narrative || '';

  reviewNarrativeEdit.value = reviewNarrativeText.textContent;

  revCategory.textContent = d.category || 'Not provided';
  revSubcategory.textContent = d.subcategory || 'Not provided';
  revDatetime.textContent = d.datetime ? d.datetime.replace('T', ', ') : 'Not provided';
  revAmount.textContent = d.amount !== null && d.amount !== undefined && d.amount !== '' ? `₹ ${Number(d.amount).toLocaleString('en-IN')}` : 'Not provided';
  revPlatform.textContent = d.platform || 'Not provided';
  revBank.textContent = d.bank || 'Not provided';
  revUtr.textContent = d.utr || 'Not provided';
  revSuspect.textContent = d.suspect || 'Not provided';

  const revAge = document.getElementById('rev-age');
  if (revAge) {
    const ageVal = d.age;
    if (!ageVal) {
      revAge.textContent = 'Not provided';
    } else if (ageVal < 18) {
      revAge.innerHTML = `<span style="color:#dc2626; font-weight:700;">Under 18 (${ageVal} years)</span>`;
    } else {
      revAge.textContent = `${ageVal} yrs (Adult)`;
    }
  }

  const revPoliceStation = document.getElementById('rev-police-station');
  if (revPoliceStation) {
    const dist = d.district || '';
    if (!dist && !d.state) {
      revPoliceStation.textContent = 'Location not provided';
    } else if (dist.toLowerCase().includes('mumbai')) {
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
  if (!evidenceReviewIsCurrent()) {
    showToast('Review and confirm the evidence cross-check before continuing.');
    if (state.evidenceFiles.length && state.evidenceReview?.typedText !== currentCitizenStatement()) await reconcileUploadedEvidence();
    return;
  }
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
          complainant_age: state.draft.age || null,
          state: state.draft.state || null,
          district: state.draft.district || null
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

  resSummaryText.textContent = `The app suggests "${subCat}" based on the details provided. Review the draft and evidence; this is not an official decision.`;

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
    resStatuteTags.textContent = 'No legal references were returned. Ask a qualified professional to verify any that may apply.';
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
  showToast("Preparing complaint draft PDF...");
  try {
    const res = await fetch('/api/generate_pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lost_amount: state.draft.amount || null,
        bank_name: state.draft.bank || '',
        utr_number: state.draft.utr || '',
        suspect_identifier: state.draft.suspect || '',
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

function ocrValues(value) {
  const values = Array.isArray(value) ? value : [value];
  return values.map(item => {
    if (item && typeof item === 'object' && Object.prototype.hasOwnProperty.call(item, 'value')) return String(item.value);
    return item == null ? '' : String(item);
  }).filter(Boolean);
}

function ocrTargetForField(key) {
  return ({ amount: manAmount, transaction_ref: manUtr, utr_number: manUtr,
    bank_name: manBank, payment_app: manPlatform, upi_id: manSuspect })[key] || null;
}

function currentCitizenStatement() {
  const turns = state.history.filter(message => message.role === 'user').map(message => message.content).filter(Boolean);
  if (turns.length) return turns.join('\n\n').trim();
  return (manDescription?.value || state.draft.narrative || inputVoiceText?.value || '').trim();
}

function evidenceReviewIsCurrent() {
  return !state.evidenceFiles.length || Boolean(
    state.evidenceReview?.confirmed && state.evidenceReview.typedText === currentCitizenStatement()
  );
}

async function reconcileUploadedEvidence() {
  if (!state.evidenceFiles.length) return;
  const typedText = currentCitizenStatement();
  const entities = {};
  state.evidenceFiles.forEach(file => {
    Object.entries(file.entities || {}).forEach(([key, value]) => {
      entities[key] = [...new Set([...(entities[key] ? ocrValues(entities[key]) : []), ...ocrValues(value)])];
    });
  });
  state.evidenceReview = { typedText, entities, result: null, choices: {}, confirmed: false, reviewedEntities: null, loading: true };
  renderEvidenceOcrStatus('Checking the complaint against the readable evidence…', 'evidence-ocr-status');
  renderEvidenceOcrStatus('Checking the complaint against the readable evidence…', 'voice-evidence-ocr-status');
  try {
    const response = await fetch('/api/evidence/reconcile', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ typed_narrative: typedText, ocr_entities: entities })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || result.error || 'Evidence cross-check failed.');
    state.evidenceReview.result = result;
  } catch (error) {
    state.evidenceReview.error = error.message;
  } finally {
    state.evidenceReview.loading = false;
    renderEvidenceOcrStatus('', 'evidence-ocr-status');
    renderEvidenceOcrStatus('', 'voice-evidence-ocr-status');
  }
}

function confirmEvidenceReview() {
  const review = state.evidenceReview;
  if (!review || review.loading || review.typedText !== currentCitizenStatement()) return;
  const conflicts = review.result?.conflicts || [];
  if (conflicts.some(conflict => !review.choices[conflict.field])) {
    showToast('Choose which value is correct for every flagged difference.');
    return;
  }
  const reviewed = { ...review.entities };
  conflicts.forEach(conflict => {
    if (review.choices[conflict.field] === 'statement') {
      delete reviewed[conflict.field];
      if (conflict.field === 'amount' && manAmount?.value) state.draft.amount = manAmount.value;
    } else if (review.choices[conflict.field] === 'evidence') {
      reviewed[conflict.field] = [conflict.ocr_value];
      const target = ({ amount: 'amount', transaction_ref: 'transaction_ref', utr: 'transaction_ref', rrn: 'transaction_ref', date: 'date', time: 'time' })[conflict.field];
      if (target) applyOcrReading(target, conflict.ocr_value);
    }
  });
  review.reviewedEntities = reviewed;
  review.confirmed = true;
  renderEvidenceOcrStatus('Evidence cross-check confirmed.', 'evidence-ocr-status');
  renderEvidenceOcrStatus('Evidence cross-check confirmed.', 'voice-evidence-ocr-status');
  showToast('Evidence cross-check confirmed. You can continue.');
}

function applyOcrReading(key, value) {
  if (key === 'date' || key === 'time') {
    mergeOcrDateTime(key, value);
    updateChecklistDisplay(); syncToReviewDisplay();
    showToast(`Copied OCR reading to incident ${key}.`);
    return;
  }
  const target = ocrTargetForField(key);
  if (!target) return;
  let reading = value;
  if (key === 'amount') {
    reading = String(value).replace(/[₹,\s]/g, '').replace(/^Rs\.?/i, '');
    if (!/^\d+(\.\d+)?$/.test(reading)) {
      showToast('The amount could not be entered safely. Please type it in the form.');
      return;
    }
  }
  target.value = reading;
  if (target === manAmount) state.draft.amount = reading;
  if (target === manUtr) state.draft.utr = reading;
  if (target === manSuspect) state.draft.suspect = reading;
  if (target === manBank) {
    state.draft.bank = reading;
    state.counselorDocket.bank_name = reading;
  }
  if (target === manPlatform) {
    state.draft.platform = reading;
    state.counselorDocket.platform_involved = reading;
  }
  if (target === manUtr) state.counselorDocket.utr_number = reading;
  if (target === manAmount) state.counselorDocket.financial_loss_amount = Number(reading);
  state.counselorDocket.evidence_available = true;
  state.draft.evidence = 'Screenshot / receipt uploaded';
  syncToManualForm();
  syncToReviewDisplay();
  updateChecklistDisplay();
  showToast(`Copied OCR reading to ${key.replaceAll('_', ' ')}.`);
}

function mergeOcrDateTime(key, value) {
  // Remove previously applied OCR components before adding the current
  // selection, so reapplying a reading never duplicates it in the draft.
  let retained = String(state.draft.datetime || '').trim();
  Object.values(state.ocrDateTimeValues).filter(Boolean).forEach(previous => {
    retained = retained.split(previous).join(' ').replace(/\s+/g, ' ').trim();
  });
  state.ocrDateTimeValues[key] = String(value || '').trim();
  state.draft.datetime = [retained, state.ocrDateTimeValues.date, state.ocrDateTimeValues.time]
    .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  state.counselorDocket.date_time_of_incident = state.draft.datetime;
}

function renderEvidenceOcrStatus(message = '', panelId = 'evidence-ocr-status') {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  panel.replaceChildren();
  panel.hidden = false;
  if (message) {
    const status = document.createElement('p');
    status.textContent = message;
    panel.appendChild(status);
  }
  state.evidenceFiles.forEach(fileRecord => {
    const fileTools = document.createElement('div');
    fileTools.className = 'evidence-file-tools';
    const heading = document.createElement('p');
    heading.className = 'evidence-ocr-file';
    heading.textContent = `${fileRecord.filename}: ${fileRecord.ocr_supported === false ? 'attached' : (fileRecord.chars_read ? 'text read' : 'no readable text found')}`;
    const description = document.createElement('input');
    description.type = 'text'; description.maxLength = 300; description.placeholder = 'What does this file show? (optional)';
    description.value = fileRecord.description || ''; description.setAttribute('aria-label', `Description for ${fileRecord.filename}`);
    description.addEventListener('input', () => { fileRecord.description = description.value; });
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove';
    remove.addEventListener('click', () => { state.evidenceFiles = state.evidenceFiles.filter(item => item !== fileRecord); renderEvidenceOcrStatus('Evidence list updated.', panelId); });
    fileTools.append(heading, description, remove); panel.appendChild(fileTools);
    Object.entries(fileRecord.entities || {}).forEach(([key, value]) => {
      ocrValues(value).forEach(reading => {
        const row = document.createElement('div');
        row.className = 'evidence-ocr-reading';
        const label = document.createElement('span');
        label.textContent = `${key.replaceAll('_', ' ')}: ${reading}`;
        row.appendChild(label);
        if (ocrTargetForField(key) || key === 'date' || key === 'time') {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = 'Use this';
          button.addEventListener('click', () => {
            if (button.disabled) return;
            button.disabled = true;
            button.textContent = 'Applied';
            applyOcrReading(key, reading);
          });
          row.appendChild(button);
        }
        panel.appendChild(row);
      });
    });
    if (fileRecord.raw_snippet) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Show text read from the image';
      const raw = document.createElement('p');
      raw.textContent = fileRecord.raw_snippet;
      details.append(summary, raw);
      panel.appendChild(details);
    }
    if (fileRecord.ocr_supported !== false && fileRecord.ocr_errors?.length) {
      const error = document.createElement('p');
      error.textContent = 'OCR is unavailable on this computer. The image is attached; its text was not extracted.';
      panel.appendChild(error);
    }
  });
  if (state.evidenceFiles.length) {
    const review = state.evidenceReview;
    const check = document.createElement('section');
    check.className = 'evidence-cross-check';
    const title = document.createElement('strong');
    title.textContent = 'Check extracted details against your description';
    check.appendChild(title);
    if (review?.loading) {
      const status = document.createElement('p'); status.textContent = 'Checking…'; check.appendChild(status);
    } else if (review?.error) {
      const status = document.createElement('p'); status.textContent = review.error; check.appendChild(status);
    } else if (!review || review.typedText !== currentCitizenStatement()) {
      const status = document.createElement('p'); status.textContent = 'Your description changed after this check. Run the cross-check again before continuing.'; check.appendChild(status);
    } else {
      (review.result?.conflicts || []).forEach((conflict, index) => {
        const row = document.createElement('div'); row.className = 'evidence-conflict-row';
        const detail = document.createElement('p');
        detail.textContent = `${conflict.field.replaceAll('_', ' ')} differs: your description mentions ${conflict.typed_mentions?.join(', ') || 'a different value'}; the evidence shows ${conflict.ocr_value}. Which should the draft use?`;
        const statement = document.createElement('button'); statement.type = 'button'; statement.textContent = 'Use my description';
        statement.classList.toggle('selected', review.choices[conflict.field] === 'statement');
        statement.addEventListener('click', () => { review.choices[conflict.field] = 'statement'; renderEvidenceOcrStatus('', panelId); });
        const evidence = document.createElement('button'); evidence.type = 'button'; evidence.textContent = 'Use evidence reading';
        evidence.classList.toggle('selected', review.choices[conflict.field] === 'evidence');
        evidence.addEventListener('click', () => { review.choices[conflict.field] = 'evidence'; renderEvidenceOcrStatus('', panelId); });
        row.append(detail, statement, evidence); check.appendChild(row);
      });
      if (review.result?.agreements?.length) {
        const agreements = document.createElement('p'); agreements.textContent = `${review.result.agreements.length} detail(s) agree between the description and evidence.`; check.appendChild(agreements);
      }
      if (review.result?.gaps?.length) {
        const gaps = document.createElement('p'); gaps.textContent = `Not found in either source: ${review.result.gaps.map(gap => gap.replaceAll('_', ' ')).join(', ')}.`; check.appendChild(gaps);
      }
      const confirm = document.createElement('button'); confirm.type = 'button'; confirm.textContent = review.confirmed ? 'Cross-check confirmed' : 'Confirm evidence details';
      confirm.disabled = review.confirmed;
      confirm.addEventListener('click', confirmEvidenceReview);
      check.appendChild(confirm);
    }
    const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Recheck against description';
    retry.disabled = Boolean(review?.loading);
    retry.addEventListener('click', reconcileUploadedEvidence); check.appendChild(retry);
    panel.appendChild(check);
  }
}

function applyOcrEntitiesToIntake(entities = {}) {
  const confidenceValue = value => (Array.isArray(value) ? value : [value])
    .map(item => item && typeof item === 'object' ? { text: String(item.value || ''), confidence: Number(item.confidence ?? 1) } : { text: String(item || ''), confidence: 1 })
    .find(item => item.text && item.confidence >= 0.7)?.text;
  const current = state.draft;
  const mappings = [
    ['amount', 'amount', current.amount !== null && current.amount !== undefined && current.amount !== ''],
    ['transaction_ref', 'transaction_ref', Boolean(current.utr)],
    ['bank_name', 'bank_name', Boolean(current.bank)],
    ['payment_app', 'payment_app', Boolean(current.platform)],
  ];
  mappings.forEach(([entity, target, alreadyKnown]) => {
    const value = confidenceValue(entities[entity]);
    if (value && !alreadyKnown) applyOcrReading(target, value);
  });
  const recognizedBank = confidenceValue(entities.bank_name);
  const recognizedApp = confidenceValue(entities.payment_app);
  if (!recognizedBank && recognizedApp && !current.bank) {
    current.bank = recognizedApp;
    state.counselorDocket.bank_name = recognizedApp;
    manBank.value = recognizedApp;
  }
  const date = confidenceValue(entities.date), time = confidenceValue(entities.time);
  if ((date || time) && !current.datetime) {
    if (date) mergeOcrDateTime('date', date);
    if (time) mergeOcrDateTime('time', time);
  }
  if (entities.upi_id && !current.suspect) {
    const upi = confidenceValue(entities.upi_id);
    if (upi) { current.suspect = upi; state.counselorDocket.suspect_details = upi; }
  }
  current.evidence = 'Screenshot / receipt uploaded';
  state.counselorDocket.evidence_available = true;
  updateChecklistDisplay(); syncToManualForm(); syncToReviewDisplay();
}

async function uploadEvidenceFiles(files, panelId = 'evidence-ocr-status') {
  let uploadedAny = false;
  const supportedExtensions = new Set(['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt', '.mp4', '.wav', '.mp3', '.m4a', '.ogg', '.flac', '.docx', '.xlsx', '.csv']);
  for (const file of Array.from(files || [])) {
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    const extension = `.${file.name.split('.').pop().toLowerCase()}`;
    const isImage = file.type.startsWith('image/') || ['.png', '.jpg', '.jpeg', '.webp'].includes(extension);
    if (!supportedExtensions.has(extension)) {
      showToast(`${file.name}: choose a supported image, PDF, audio, video, text, or office document.`);
      continue;
    }
    if (file.size > 25 * 1024 * 1024) {
      showToast(`${file.name}: evidence files must be 25 MB or smaller.`);
      continue;
    }
    if ((isImage || isPdf) && file.size > 5 * 1024 * 1024) {
      showToast(`${file.name}: images and PDFs for OCR must be 5 MB or smaller.`);
      continue;
    }
    renderEvidenceOcrStatus(`Uploading ${file.name} and reading its text…`, panelId);
    const formData = new FormData();
    formData.append('file', file, file.name);
    try {
      const response = await fetch('/api/upload_evidence', { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.detail || data.error || `Upload failed (${response.status}).`);
      state.evidenceFiles.push({
        filename: data.filename || file.name,
        chars_read: data.chars_read || 0,
        entities: data.entities || {},
        raw_snippet: data.raw_snippet || '',
        ocr_errors: data.ocr_errors || [],
        ocr_supported: data.ocr_supported !== false
      });
      uploadedAny = true;
      applyOcrEntitiesToIntake(data.entities || {});
      Object.entries(data.entities || {}).forEach(([key, value]) => {
        state.ocrEntities[key] = [...new Set([...(state.ocrEntities[key] ? ocrValues(state.ocrEntities[key]) : []), ...ocrValues(value)])];
        const target = ocrTargetForField(key);
        const readings = ocrValues(value);
        if (target && !target.value && readings.length === 1) applyOcrReading(key, readings[0]);
      });
      renderEvidenceOcrStatus('Evidence attached. Readable values have been filled where blank. Check each value before continuing.', panelId);
    } catch (error) {
      renderEvidenceOcrStatus(`Could not process ${file.name}: ${error.message}`, panelId);
    }
  }
  if (uploadedAny) {
    await reconcileUploadedEvidence();
    renderEvidenceOcrStatus('Evidence attached. Check the OCR values and confirm the cross-check before continuing.', panelId);
  }
  return uploadedAny;
}

function additionalRowValues(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return [];
  return [...container.querySelectorAll('[data-repeat-row]')].map(row => {
    const values = {};
    row.querySelectorAll('[data-field]').forEach(input => { values[input.dataset.field] = input.value.trim(); });
    return values;
  });
}

function collectDebitTransactions(draft) {
  const result = [];
  if (draft.amount || draft.bank || draft.utr) result.push({ amount: Number(draft.amount) || 0, bank_name: draft.bank || '', utr_number: draft.utr || '', date: draft.datetime || '' });
  additionalRowValues('additional-transaction-rows').forEach(row => {
    if (row.amount || row.bank_name || row.utr_number) result.push({ amount: Number(row.amount) || 0, bank_name: row.bank_name || '', utr_number: row.utr_number || '', date: row.date || draft.datetime || '' });
  });
  return result;
}

function collectRecipientTransactions(draft) {
  const result = [];
  if (draft.suspect) result.push({ method: /@/.test(draft.suspect) ? 'UPI' : 'Unknown', bank: '', account_no: draft.suspect, transaction_id: draft.utr || '', amount: Number(draft.amount) || 0, transaction_date: draft.datetime || '' });
  additionalRowValues('recipient-transaction-rows').forEach(row => {
    if (row.identifier || row.bank || row.transaction_id) result.push({ method: row.method || 'UPI', bank: row.bank || '', account_no: row.identifier || '', transaction_id: row.transaction_id || '', amount: Number(row.amount) || 0, transaction_date: row.date || draft.datetime || '' });
  });
  return result;
}

function addRepeatableRow(containerId, fields) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (container.children.length >= 10) { showToast('Add up to 10 additional rows.'); return; }
  const row = document.createElement('div'); row.className = 'repeatable-data-row'; row.dataset.repeatRow = 'true';
  fields.forEach(field => {
    const label = document.createElement('label'); label.textContent = field.label;
    const input = document.createElement('input'); input.type = field.type || 'text'; input.dataset.field = field.key;
    input.className = 'field-input'; input.placeholder = field.placeholder || '';
    if (field.type === 'number') { input.min = '0'; input.step = '0.01'; }
    label.appendChild(input); row.appendChild(label);
  });
  const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'btn-remove-repeat-row'; remove.textContent = 'Remove';
  remove.addEventListener('click', () => row.remove()); row.appendChild(remove); container.appendChild(row);
}

async function saveCaseRecord() {
  btnSaveContinue.disabled = true;
  btnSaveContinue.textContent = 'Saving…';
  try {
    const d = state.draft;
    if (!chkLocalConsent?.checked) throw new Error('Confirm that this record may be saved and shown in the local investigator workspace.');
    if (!evidenceReviewIsCurrent()) throw new Error('Review and confirm the evidence cross-check before saving this record.');
    d.name = document.getElementById('review-name')?.value.trim() || d.name || '';
    d.phone = document.getElementById('review-phone')?.value.trim() || d.phone || '';
    d.email = document.getElementById('review-email')?.value.trim() || d.email || '';
    if (!d.name || !d.phone) throw new Error('Add your name and phone number before saving this complaint.');
    const narrative = (d.narrative || '').trim();
    if (!narrative) throw new Error('Add an incident description before saving the complaint.');
    const rawComplaint = currentCitizenStatement() || narrative;
    const payload = {
      intake_session_id: state.sessionId,
      complainant: { name: d.name || '', phone: d.phone || '', email: d.email || '', age: d.age || null, state: d.state || '', district: d.district || '', city: d.city || d.district || '', address: d.address || '', relationship_with_victim: d.relationship || 'Self' },
      incident: {
        datetime: d.datetime || '', category: d.category || '', sub_category: d.subcategory || '',
        modus_operandi: d.platform || '', location: d.platform ? [d.platform] : []
      },
      incident_text: rawComplaint,
      standardised_narrative: narrative,
      sub_category: (state.classificationResult && state.classificationResult.predicted_category) || d.subcategory,
      entities: state.evidenceReview?.reviewedEntities || state.ocrEntities,
      transactions: collectDebitTransactions(d),
      suspect_transactions: collectRecipientTransactions(d),
      suspects: [d.suspect ? { phone: d.suspect, details: d.suspect } : null, ...additionalRowValues('recipient-transaction-rows').filter(row => row.identifier).map(row => ({ name: row.name || 'Unknown', id_type: row.method || 'Account / payment identifier', id_number: row.identifier, details: row.bank || '' }))].filter(Boolean),
      evidence: state.evidenceFiles.map(file => ({ filename: file.filename, description: file.description || '', chars_read: file.chars_read, raw_ocr_text: file.raw_snippet || '', ocr_errors: file.ocr_errors || [], ocr_entities: file.entities || {} })),
      investigator_consent: true,
      reconciliation: state.evidenceReview?.result || {},
      reviewed_evidence_entities: state.evidenceReview?.reviewedEntities || state.ocrEntities
    };
    const response = await fetch('/api/cases/submit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.detail || result.error || 'Could not save the complaint.');
    state.savedCaseReference = result.reference;
    const reference = document.getElementById('saved-case-reference');
    reference.textContent = `Saved locally. Reference: ${result.reference}`;
    reference.hidden = false;
    btnSaveContinue.textContent = 'Saved';
    showToast(`Complaint saved. Reference: ${result.reference}`);
  } catch (error) {
    btnSaveContinue.disabled = false;
    btnSaveContinue.textContent = 'Save and Continue →';
    showToast(error.message);
  }
}

// ==========================================================================
// 8. Event Listeners & Navigation Wiring
// ==========================================================================

function initEventListeners() {
  // Top Navbar Stepper Quick Tabs (Screens 3, 4, 5, 6, 7)
  stepperTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (['page-voice', 'page-manual'].includes(btn.dataset.target)) startNewComplaintIfPreviousWasSaved();
      showScreen(btn.dataset.target);
    });
  });

  // Brand logo & Dashboard links
  brandLogoBtn.addEventListener('click', () => showScreen('page-choose-mode'));
  document.getElementById('top-nav-home')?.addEventListener('click', () => showScreen('page-choose-mode'));
  document.getElementById('top-nav-help')?.addEventListener('click', () => {
    showScreen('page-choose-mode', false);
    requestAnimationFrame(() => document.getElementById('how-to-report')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  });
  document.getElementById('top-nav-prepare')?.addEventListener('click', () => {
    startNewComplaintIfPreviousWasSaved();
    showScreen('page-voice');
  });
  document.getElementById('top-nav-track')?.addEventListener('click', () => showScreen('page-track'));
  document.getElementById('btn-reviewer-workspace')?.addEventListener('click', () => {
    showScreen('page-dashboard');
    loadDashboardCases(false);
  });
  navReport.addEventListener('click', (e) => { e.preventDefault(); startNewComplaintIfPreviousWasSaved(); showScreen('page-choose-mode'); });
  navDashboard.addEventListener('click', (e) => {
    e.preventDefault();
    showScreen('page-dashboard');
    loadDashboardCases(false);
  });
  const openInvestigatorSection = (event, link, sectionId) => {
    event.preventDefault();
    showScreen('page-dashboard', false);
    navDashboard.classList.remove('active');
    link.classList.add('active');
    loadDashboardCases(false);
    requestAnimationFrame(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  navInvestigatorOperations?.addEventListener('click', event => openInvestigatorSection(event, navInvestigatorOperations, 'investigator-operations'));
  navInvestigatorImport?.addEventListener('click', event => openInvestigatorSection(event, navInvestigatorImport, 'investigator-import'));
  navTrack?.addEventListener('click', e => { e.preventDefault(); showScreen('page-track'); });

  const trackForm = document.getElementById('form-track-case');
  trackForm?.addEventListener('submit', async e => {
    e.preventDefault();
    const reference = document.getElementById('track-reference').value.trim();
    const result = document.getElementById('track-result');
    result.hidden = false;
    result.textContent = 'Checking the local case register…';
    try {
      const response = await fetch('/api/cases/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reference }) });
      const data = await response.json();
      result.replaceChildren();
      const title = document.createElement('strong');
      title.textContent = data.found ? `${data.reference} · ${formatCaseStatus(data.status)}` : 'No matching local record';
      const detail = document.createElement('p'); detail.textContent = data.found ? `${data.friendly_status} ${data.category ? `Suggested type: ${data.category}.` : ''}` : (data.message || 'Check the reference and try again.');
      result.append(title, detail);
      if (data.found && data.has_pdf && data.pdf_url) { const link = document.createElement('a'); link.href = data.pdf_url; link.textContent = 'Open saved complaint PDF'; link.target = '_blank'; link.rel = 'noopener'; result.append(link); }
    } catch (error) { result.textContent = `Could not check status: ${error.message}`; }
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
      fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId })
      }).catch(error => console.warn('Could not clear the saved intake session:', error))
        .finally(() => window.location.reload());
    }
  });

  // SCREEN 3 BUTTONS:
  btnStartVoice.addEventListener('click', () => { startNewComplaintIfPreviousWasSaved(); showScreen('page-voice'); });
  cardChooseVoice.addEventListener('click', (e) => {
    if (e.target !== btnStartVoice) { startNewComplaintIfPreviousWasSaved(); showScreen('page-voice'); }
  });

  btnStartManual.addEventListener('click', () => { startNewComplaintIfPreviousWasSaved(); showScreen('page-manual'); });
  cardChooseManual.addEventListener('click', (e) => {
    if (e.target !== btnStartManual) { startNewComplaintIfPreviousWasSaved(); showScreen('page-manual'); }
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
    if (!evidenceReviewIsCurrent()) {
      showToast('Review and confirm the evidence cross-check before continuing.');
      if (state.evidenceFiles.length) reconcileUploadedEvidence();
      return;
    }
    syncToReviewDisplay();
    showScreen('page-review');
  });

  document.getElementById('btn-add-transaction')?.addEventListener('click', () => addRepeatableRow('additional-transaction-rows', [
    { key: 'amount', label: 'Amount (INR)', type: 'number' },
    { key: 'bank_name', label: 'Bank / wallet' },
    { key: 'utr_number', label: 'Transaction ID / UTR' },
    { key: 'date', label: 'Transaction date', type: 'date' }
  ]));
  document.getElementById('btn-add-recipient')?.addEventListener('click', () => addRepeatableRow('recipient-transaction-rows', [
    { key: 'method', label: 'Payment method', placeholder: 'UPI, bank transfer, wallet…' },
    { key: 'bank', label: 'Recipient bank / app' },
    { key: 'identifier', label: 'Recipient identifier' },
    { key: 'transaction_id', label: 'Transaction ID / UTR' },
    { key: 'amount', label: 'Amount (INR)', type: 'number' },
    { key: 'date', label: 'Transaction date', type: 'date' }
  ]));

  // SCREEN 5 (MANUAL FORM) BUTTONS & CASCADING DROPDOWNS:
  manCategory.addEventListener('change', () => {
    state.draft.category = manCategory.value;
    state.draft.subcategory = '';
    populateManualSubcategories(manCategory.value);
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
    if (state.evidenceFiles.length) {
      if (state.evidenceReview) state.evidenceReview.confirmed = false;
      clearTimeout(window.evidenceReviewDebounce);
      window.evidenceReviewDebounce = setTimeout(reconcileUploadedEvidence, 500);
    }
  });

  btnManualBack.addEventListener('click', () => showScreen('page-choose-mode'));

  formManualComplaint.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitButton = document.getElementById('btn-manual-submit');
    submitButton.disabled = true;
    submitButton.textContent = 'Preparing draft…';
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
    if (manAge) state.draft.age = parseInt(manAge.value, 10) || null;
    if (manState) state.draft.state = manState.value;
    if (manDistrict) state.draft.district = manDistrict.value;
    state.draft.name = document.getElementById('man-name')?.value.trim() || '';
    state.draft.phone = document.getElementById('man-phone')?.value.trim() || '';
    state.draft.email = document.getElementById('man-email')?.value.trim() || '';
    state.draft.relationship = document.getElementById('man-relation')?.value || 'Self';
    state.draft.city = document.getElementById('man-city')?.value.trim() || state.draft.district;
    state.draft.address = document.getElementById('man-address')?.value.trim() || '';

    if (!evidenceReviewIsCurrent()) {
      submitButton.disabled = false; submitButton.textContent = 'Generate Draft with AI →';
      if (state.evidenceFiles.length) reconcileUploadedEvidence();
      showToast('Review and confirm the evidence cross-check before continuing.');
      return;
    }

    try {
      const response = await fetch('/api/intake/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: state.draft.narrative,
          user_profile: { age: state.draft.age, state: state.draft.state, district: state.draft.district },
          evidence_paths: state.evidenceFiles.map(file => file.filename)
        })
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.detail || result.error || 'Could not prepare the draft.');
      state.draft.narrative = result.standardised_narrative || state.draft.narrative;
      state.ocrEntities = { ...state.ocrEntities, ...(result.ocr_entities || {}) };
      state.intakeAnalysis = result;
      syncToReviewDisplay();
      showToast('Draft prepared. Please review the details.');
      showScreen('page-review');
    } catch (error) {
      showToast(`Could not prepare the draft: ${error.message}`);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Generate Draft with AI →';
    }
  });

  // Upload evidence to the real OCR endpoint and let the complainant choose
  // which extracted values should fill the complaint form.
  if (manFileUpload) {
    manFileUpload.addEventListener('change', async event => {
      const uploadLabel = document.querySelector('label[for="man-file-upload"] .upload-btn-text');
      if (uploadLabel) uploadLabel.textContent = 'Uploading…';
      await uploadEvidenceFiles(event.target.files);
      event.target.value = '';
      if (uploadLabel) uploadLabel.textContent = 'Upload Files';
    });
  }

  const voiceFileUpload = document.getElementById('voice-evidence-upload');
  voiceFileUpload?.addEventListener('change', async event => {
    const files = event.target.files;
    const uploaded = await uploadEvidenceFiles(files, 'voice-evidence-ocr-status');
    event.target.value = '';
    if (uploaded) {
      const uploadPanel = document.getElementById('voice-evidence-panel');
      if (uploadPanel) uploadPanel.hidden = false;
      await handleUserTurn('I uploaded the bank message or receipt. Please use the readable details from it.');
    }
  });

  const voiceNoteUpload = document.getElementById('voice-note-upload');
  voiceNoteUpload?.addEventListener('change', async event => {
    const file = event.target.files?.[0];
    const status = document.getElementById('voice-note-status');
    event.target.value = '';
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) { if (status) status.textContent = 'Voice notes must be 25 MB or smaller.'; return; }
    if (status) status.textContent = 'Transcribing voice note locally…';
    const form = new FormData(); form.append('audio', file, file.name); form.append('language', state.currentLang);
    try {
      const response = await fetch('/api/transcribe_audio', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok || !result.ok || !result.text?.trim()) throw new Error(result.error || result.detail || 'No speech was recognized.');
      inputVoiceText.value = result.text.trim();
      inputVoiceText.focus();
      if (status) status.textContent = 'Transcript ready. Edit it if needed, then send it to the assistant.';
    } catch (error) {
      if (status) status.textContent = `Could not transcribe the voice note: ${error.message}`;
    }
  });

  inputVoiceText.addEventListener('input', () => {
    if (!state.evidenceFiles.length) return;
    if (state.evidenceReview) state.evidenceReview.confirmed = false;
    clearTimeout(window.evidenceReviewDebounce);
    window.evidenceReviewDebounce = setTimeout(reconcileUploadedEvidence, 500);
  });

  // MODULE F: DASHBOARD EVENT LISTENERS
  const btnRefresh = document.getElementById('btn-refresh-cases');
  if (btnRefresh) btnRefresh.addEventListener('click', loadDashboardCases);

  const dashSearch = document.getElementById('dash-search-input');
  if (dashSearch) dashSearch.addEventListener('input', applyDashboardFilters);

  const dashCat = document.getElementById('dash-category-filter');
  if (dashCat) dashCat.addEventListener('change', applyDashboardFilters);

  const dashUrg = document.getElementById('dash-urgency-filter');
  if (dashUrg) dashUrg.addEventListener('change', applyDashboardFilters);
  const dashStatus = document.getElementById('dash-status-filter');
  if (dashStatus) dashStatus.addEventListener('change', applyDashboardFilters);

  const btnCloseModal = document.getElementById('btn-close-modal');
  document.getElementById('btn-load-benchmark')?.addEventListener('click', loadBenchmark);
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', () => {
      const modal = document.getElementById('modal-case-inspector');
      if (modal) modal.style.display = 'none';
    });
  }

  const importCaseForm = document.getElementById('form-import-case');
  importCaseForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const caseFile = document.getElementById('import-case-file').files?.[0];
    const evidenceFiles = document.getElementById('import-evidence-files').files || [];
    const submit = document.getElementById('btn-import-case');
    const status = document.getElementById('import-case-status');
    if (!caseFile) return;
    submit.disabled = true; status.textContent = 'Importing case and evidence…';
    try {
      const form = new FormData(); form.append('case_file', caseFile, caseFile.name);
      Array.from(evidenceFiles).forEach(file => form.append('evidence_files', file, file.name));
      const response = await fetch('/api/cases/import', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.detail || result.error || 'Import failed.');
      status.textContent = `Case ${result.reference} was added to the local review queue.`;
      importCaseForm.reset(); await loadDashboardCases();
    } catch (error) { status.textContent = error.message; }
    finally { submit.disabled = false; }
  });

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
  chkLocalConsent?.addEventListener('change', () => { btnSaveContinue.disabled = !chkLocalConsent.checked; });
  btnSaveContinue.addEventListener('click', () => {
    if (state.savedCaseReference) {
      showScreen('page-choose-mode');
      return;
    }
    saveCaseRecord();
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

function caseNarrative(c) {
  const candidates = [
    c?.narrative,
    c?.complaint?.standardised_narrative,
    c?.complaint?.narrative,
    c?.raw_complaint,
    c?.complaint?.raw_text
  ];
  return candidates.find(value => {
    const text = String(value || '').trim();
    return text && !['not supplied', 'NOT AVAILABLE - Module A did not run'].includes(text);
  }) || '';
}

function caseRawComplaint(c) {
  const raw = c?.raw_complaint || c?.complaint?.raw_text || '';
  const text = String(raw).trim();
  return text && text !== 'not supplied' ? text : '';
}

function formatCaseStatus(status) {
  const value = String(status || 'RECEIVED - AWAITING REVIEW');
  const labels = {
    'RECEIVED - AWAITING REVIEW': 'Waiting for review',
    'IN REVIEW': 'In review',
    'AWAITING INFORMATION': 'Waiting for information',
    'REFERRED FOR FOLLOW-UP': 'Follow-up needed',
    'REVIEW COMPLETE': 'Review complete',
    'CATEGORY REVIEWED': 'Category reviewed',
    'CONFIRMED BY OFFICER': 'Review complete',
    'RECLASSIFIED BY OFFICER': 'Category updated'
  };
  return labels[value] || value.replace(/_/g, ' ').toLowerCase();
}

// ==========================================================================
// 9. Module F: Law Enforcement / Officer Dashboard & Case Inspector
// ==========================================================================

async function loadDashboardCases(showRefreshToast = true) {
  const btn = document.getElementById('btn-refresh-cases');
  if (btn) btn.textContent = '⏳ Refreshing...';

  try {
    const res = await fetch('/api/cases');
    if (!res.ok) throw new Error("Failed to load cases: " + res.statusText);
    const data = await res.json();
    
    state.allDashboardCases = data.cases || [];
    const stats = data.stats || {};
    renderOperationsSummary(state.allDashboardCases);

    // Update KPI Metric Cards
    const elTotal = document.getElementById('stat-total-cases');
    const elGolden = document.getElementById('stat-golden-hour');
    const elLoss = document.getElementById('stat-total-loss');
    const elPending = document.getElementById('stat-pending-cases');
    const elEvidenceConflicts = document.getElementById('stat-evidence-conflicts');

    if (elTotal) elTotal.textContent = stats.total_cases !== undefined ? stats.total_cases : state.allDashboardCases.length;
    if (elGolden) elGolden.textContent = stats.golden_hour_count !== undefined ? stats.golden_hour_count : 0;
    if (elLoss) elLoss.textContent = `₹ ${Number(stats.total_loss_inr || 0).toLocaleString('en-IN')}`;
    if (elPending) elPending.textContent = stats.pending_count !== undefined ? stats.pending_count : 0;
    if (elEvidenceConflicts) elEvidenceConflicts.textContent = stats.conflict_count !== undefined ? stats.conflict_count : 0;

    applyDashboardFilters();
    if (showRefreshToast) showToast("Investigator queue refreshed.");
  } catch (err) {
    showToast("Error loading cases: " + err.message);
  } finally {
    if (btn) btn.textContent = 'Refresh records';
  }
}

function applyDashboardFilters() {
  const searchInput = document.getElementById('dash-search-input');
  const catFilter = document.getElementById('dash-category-filter');
  const urgFilter = document.getElementById('dash-urgency-filter');
  const statusFilter = document.getElementById('dash-status-filter');

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const selectedCat = catFilter ? catFilter.value : '';
  const selectedUrg = urgFilter ? urgFilter.value : '';
  const selectedStatus = statusFilter ? statusFilter.value : '';

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
  if (selectedStatus) list = list.filter(c => (c.status || 'RECEIVED - AWAITING REVIEW') === selectedStatus);

  if (query) {
    list = list.filter(c => {
      const ref = (c.reference || '').toLowerCase();
      const comp = (c.complainant?.name || '').toLowerCase();
      const phone = (c.complainant?.phone || '').toLowerCase();
      const sub = (c.classification?.sub_category || '').toLowerCase();
      const ps = (c.complainant?.police_station || '').toLowerCase();
      const narr = `${caseNarrative(c)} ${caseRawComplaint(c)}`.toLowerCase();
      return ref.includes(query) || comp.includes(query) || phone.includes(query) || sub.includes(query) || ps.includes(query) || narr.includes(query);
    });
  }

  renderCasesTable(list);
}

function renderOperationsSummary(cases) {
  const target = document.getElementById('operations-summary');
  if (!target) return;
  const statuses = new Map(), categories = new Map();
  (cases || []).forEach(c => {
    const status = c.status || 'RECEIVED - AWAITING REVIEW';
    const category = c.classification?.sub_category || c.incident?.category || 'Unclassified';
    statuses.set(status, (statuses.get(status) || 0) + 1);
    categories.set(category, (categories.get(category) || 0) + 1);
  });
  target.replaceChildren();
  if (!cases?.length) { target.textContent = 'No records are available for the operations summary.'; return; }
  const addGroup = (heading, entries) => {
    const section = document.createElement('div'); section.className = 'operations-chart';
    const title = document.createElement('h3'); title.textContent = heading; section.appendChild(title);
    const max = Math.max(1, ...entries.map(([, count]) => count));
    entries.forEach(([label, count]) => {
      const row = document.createElement('div'); row.className = 'operations-chart-row';
      const caption = document.createElement('span'); caption.textContent = `${label} (${count})`;
      const bar = document.createElement('progress'); bar.max = max; bar.value = count; bar.setAttribute('aria-label', `${label}: ${count} records`);
      row.append(caption, bar); section.appendChild(row);
    });
    target.appendChild(section);
  };
  addGroup('Cases by status', [...statuses].sort((a,b) => b[1]-a[1]));
  addGroup('Cases by suggested type', [...categories].sort((a,b) => b[1]-a[1]).slice(0,6));
}

async function loadBenchmark() {
  const output = document.getElementById('benchmark-summary');
  if (!output) return;
  output.textContent = 'Loading benchmark…';
  try {
    const response = await fetch('/api/benchmark');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Benchmark data is unavailable.');
    const metrics = data.overall_metrics || {};
    const pct = value => Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(2)}%` : '—';
    output.replaceChildren();
    const summary = document.createElement('p');
    summary.textContent = `Evaluation ${data._meta?.eval_date || 'date not recorded'} · accuracy ${pct(metrics.accuracy)} · macro F1 ${pct(metrics.macro_f1)} · ${Number(data._meta?.test_split_size || 0).toLocaleString()} test examples · ${data._meta?.num_classes || '—'} categories. Dataset results do not guarantee an individual prediction.`;
    output.appendChild(summary);
    const appendTable = (title, headers, rows) => {
      if (!rows?.length) return;
      const details = document.createElement('details');
      const heading = document.createElement('summary'); heading.textContent = title; details.appendChild(heading);
      const scroll = document.createElement('div'); scroll.className = 'benchmark-table-scroll';
      const table = document.createElement('table'); table.className = 'benchmark-data-table';
      const head = document.createElement('tr'); headers.forEach(value => { const cell = document.createElement('th'); cell.textContent = value; head.appendChild(cell); });
      const thead = document.createElement('thead'); thead.appendChild(head); table.appendChild(thead);
      const tbody = document.createElement('tbody');
      rows.forEach(values => { const row = document.createElement('tr'); values.forEach(value => { const cell = document.createElement('td'); cell.textContent = String(value ?? '—'); row.appendChild(cell); }); tbody.appendChild(row); });
      table.appendChild(tbody); scroll.appendChild(table); details.appendChild(scroll); output.appendChild(details);
    };
    appendTable('Model comparison', ['Model', 'Accuracy', 'Macro F1', 'Training time'], Object.entries(data.model_comparison || {}).map(([name, value]) => [name, pct(value.accuracy), Number(value.macro_f1 || 0).toFixed(4), `${Number(value.train_time_sec || 0).toFixed(2)} s`]));
    appendTable('Per-category scores', ['Category', 'Precision', 'Recall', 'F1', 'Support'], (data.per_class_metrics || []).map(item => [item.category, pct(item.precision), pct(item.recall), pct(item.f1_score), item.support]));
    appendTable('Most common category confusions', ['Actual', 'Suggested', 'Count'], (data.top_confusion_pairs || []).map(item => [item.true_category, item.predicted_category, item.count]));
    const matrix = data.confusion_matrix || [];
    if (data.classes?.length && matrix.length) appendTable('Confusion matrix (rows are actual categories)', ['Actual / suggested', ...data.classes], matrix.map((row, index) => [data.classes[index], ...row]));
  } catch (error) { output.textContent = `Benchmark unavailable: ${error.message}`; }
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
        <td colspan="11" style="text-align: center; padding: 2.5rem; color: #64748b;">
          No saved complaint records match this search.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = cases.map(c => {
    const ref = c.reference || 'CYB-REF';
    const dateStr = (c.incident_datetime || c.generated_at || '—').slice(0, 16).replace('T', ' ');
    const compName = c.complainant?.name || 'Not provided';
    const compPhone = c.complainant?.phone ? `(${c.complainant.phone})` : '';
    const subCat = c.classification?.sub_category || c.incident?.category || 'Not classified';
    const ps = c.complainant?.police_station || c.complainant?.city || 'Not provided';
    
    // Total loss calculation
    let lossVal = 0;
    (c.transactions || []).forEach(t => {
      lossVal += parseFloat(t.amount || 0) || 0;
    });
    const lossDisplay = lossVal > 0 ? `₹ ${lossVal.toLocaleString('en-IN')}` : '—';

    // Urgency pill
    const isGolden = c.sentiment?.is_golden_hour || (c.sentiment?.urgency_level || '').includes('GOLDEN');
    const rawUrgency = c.sentiment?.urgency_level || 'STANDARD';
    const urgLvl = isGolden ? 'Urgent' : rawUrgency.includes('HIGH') ? 'High' : 'Standard';
    const urgBadge = isGolden 
      ? `<span class="badge-golden-hour">🚨 ${escapeHtml(urgLvl)}</span>`
      : `<span class="badge-standard">${escapeHtml(urgLvl)}</span>`;

    // Status pill
    const status = c.status || 'RECEIVED - AWAITING REVIEW';
    const displayStatus = formatCaseStatus(status);
    const conflicts = c.reconciliation?.conflicts || [];
    const evidenceCheck = conflicts.length
      ? `<span class="queue-evidence-flag" title="${conflicts.length} difference(s) need investigator review">Review ${conflicts.length} difference${conflicts.length === 1 ? '' : 's'}</span>`
      : (c.received_evidence_files?.length || c.evidence?.attachments?.length)
        ? '<span class="queue-evidence-ok">Evidence attached</span>'
        : '<span class="queue-evidence-none">No evidence</span>';
    let statusStyle = 'background:#fef3c7; color:#92400e; border:1px solid #fde68a;';
    if (status.includes('CONFIRMED')) {
      statusStyle = 'background:#dcfce7; color:#166534; border:1px solid #bbf7d0;';
    } else if (status.includes('RECLASSIFIED')) {
      statusStyle = 'background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe;';
    }

    return `
      <tr>
        <td style="font-family: monospace; font-weight: 700;">
          <a href="#" data-case-reference="${escapeHtml(ref)}" style="color: #2563eb; text-decoration: underline;">
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
            ${escapeHtml(displayStatus)}
          </span>
        </td>
        <td>${escapeHtml(c.assigned_to || 'Unassigned')}</td>
        <td>${evidenceCheck}</td>
        <td style="white-space: nowrap;">
          <button type="button" class="btn-inspect-case" data-case-reference="${escapeHtml(ref)}">
            View details
          </button>
        </td>
      </tr>
    `;
  }).join('');
  tbody.querySelectorAll('[data-case-reference]').forEach(element => {
    element.addEventListener('click', event => {
      event.preventDefault(); inspectCaseDetail(element.dataset.caseReference);
    });
  });
}

async function inspectCaseDetail(caseRef) {
  const modal = document.getElementById('modal-case-inspector');
  const modalRef = document.getElementById('modal-case-ref');
  const modalSub = document.getElementById('modal-case-sub');
  const modalBody = document.getElementById('modal-case-body');
  const modalFooter = document.getElementById('modal-case-footer');

  if (!modal || !modalBody) return;

  modalRef.textContent = `Case Reference: ${caseRef}`;
  modalSub.textContent = `Loading saved complaint record...`;
  modalBody.innerHTML = `<div style="text-align:center; padding: 3rem; color: #64748b;">Loading record details and evidence...</div>`;
  modalFooter.innerHTML = '';
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/cases/${encodeURIComponent(caseRef)}`);
    if (!res.ok) throw new Error("Failed to load case detail: " + res.statusText);
    const c = await res.json();

    const safeRef = (c.reference || caseRef).replace(/[^A-Za-z0-9_-]/g, '-');
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

    const recipientTransactionsHtml = (c.suspect_transactions || []).length
      ? c.suspect_transactions.map(t => `<div class="investigator-detail-row"><strong>${escapeHtml(t.method || 'Transfer')}</strong> · ${escapeHtml(t.bank || 'Recipient bank/app not supplied')} · ${escapeHtml(t.account_no || 'Recipient identifier not supplied')} · UTR ${escapeHtml(t.transaction_id || 'Not supplied')} · ₹${Number(t.amount || 0).toLocaleString('en-IN')} · ${escapeHtml(t.transaction_date || 'Date not supplied')}</div>`).join('')
      : '<p class="field-hint">No recipient transaction details supplied.</p>';

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

    const attachedEvidence = c.received_evidence_files?.length
      ? c.received_evidence_files.map(file => ({ filename: file.name }))
      : (c.evidence?.attachments || c.evidence?.table || []);
    const evidenceHtml = attachedEvidence.length
      ? attachedEvidence.map(item => {
          const filename = typeof item === 'string' ? item : item.filename;
          if (!filename) return '';
          const url = `/api/evidence/${encodeURIComponent(filename)}`;
          const entities = item.ocr_entities || item.entities || {};
          const readings = Object.entries(entities).flatMap(([key, value]) =>
            ocrValues(value).map(reading => `${key.replaceAll('_', ' ')}: ${reading}`)
          );
          const rawOcr = item.raw_ocr_text || item.raw_snippet || '';
          return `<div style="padding:6px 0; border-top:1px solid #e2e8f0; font-size:0.84rem;">
            <a href="${url}" target="_blank" rel="noopener">${escapeHtml(filename)}</a>
            ${item.chars_read ? `<div class="field-hint">OCR read ${Number(item.chars_read)} characters</div>` : ''}
            ${readings.length ? `<div class="field-hint">Extracted: ${escapeHtml(readings.join(' · '))}</div>` : ''}
            ${rawOcr ? `<details><summary>OCR text preview</summary><pre class="evidence-ocr-preview">${escapeHtml(rawOcr)}</pre></details>` : ''}
          </div>`;
        }).join('')
      : '<p style="color:#64748b; font-size:0.85rem;">No evidence files are attached to this case.</p>';

    // Legal sections
    let legalHtml = '';
    if (c.legal_sections) {
      const bns = (c.legal_sections.bns || []).map(s => `<span class="statute-tag">BNS Sec ${s.section}: ${s.description}</span>`).join(' ');
      const it = (c.legal_sections.it_act || []).map(s => `<span class="statute-tag">IT Act Sec ${s.section}: ${s.description}</span>`).join(' ');
      const other = (c.legal_sections.other || []).map(s => `<span class="statute-tag" style="background:#fee2e2; color:#991b1b; border-color:#fca5a5;">⚠️ ${s.act} Sec ${s.section}: ${s.description}</span>`).join(' ');
      legalHtml = bns + ' ' + it + ' ' + other;
    }
    if (!legalHtml) legalHtml = '<span style="color:#64748b;font-size:0.85rem;">No legal references recorded.</span>';

    const reconciliation = c.reconciliation || {};
    const reconciliationHtml = reconciliation.has_conflicts && reconciliation.conflicts?.length
      ? reconciliation.conflicts.map(conflict => `<div class="evidence-conflict-row"><strong>${escapeHtml(String(conflict.field || 'Detail').replaceAll('_', ' '))}</strong><p>Evidence: ${escapeHtml(conflict.ocr_value || '—')} · Complaint text: ${escapeHtml((conflict.typed_mentions || []).join(', ') || '—')}</p><span>${escapeHtml(conflict.resolution || 'Check both sources before relying on either value.')}</span></div>`).join('')
      : reconciliation.agreements?.length
        ? `<p>${reconciliation.agreements.length} detail(s) match the complaint text. ${escapeHtml(reconciliation.confidence_note || '')}</p>`
        : '<p class="field-hint">No conflict was recorded. Review the original evidence before relying on extracted details.</p>';
    const categoryOptions = [...new Set(Object.values(NCRP_TAXONOMY).flat())];

    modalBody.innerHTML = `
      <div class="investigator-case-grid">
        <div class="investigator-case-column">
          <div class="investigator-detail-card">
            <h4>Complainant details</h4>
            <div class="investigator-field-row"><span>Name</span><strong>${escapeHtml(c.complainant?.name || 'Not provided')}</strong></div>
            <div class="investigator-field-row"><span>Phone</span><strong>${escapeHtml(c.complainant?.phone || 'Not provided')}</strong></div>
            <div class="investigator-field-row"><span>Age</span><strong>${c.complainant?.age ? `${c.complainant.age} years` : 'Not provided'}</strong></div>
            <div class="investigator-field-row"><span>Police station</span><strong>${escapeHtml(c.complainant?.police_station || 'Not provided')}</strong></div>
            <div class="investigator-field-row"><span>City / State</span><strong>${escapeHtml([c.complainant?.city, c.complainant?.state].filter(Boolean).join(', ') || 'Not provided')}</strong></div>
          </div>

          <div class="investigator-detail-card">
            <h4>Suggested legal references to verify</h4>
            <div class="statute-tags-flex">
              ${legalHtml}
            </div>
            <div class="investigator-note">
              These possible references need professional review.
            </div>
          </div>

          <div class="investigator-detail-card">
            <h4>Reported debit transactions</h4>
            ${txnsHtml}
          </div>
          <div class="investigator-detail-card"><h4>Recipient transaction trail</h4>${recipientTransactionsHtml}</div>
        </div>

        <div class="investigator-case-column">
          <div class="investigator-detail-card">
            <h4>Complaint summary</h4>
            <div class="investigator-narrative">
              ${escapeHtml(caseNarrative(c) || 'No complaint narrative was saved for this case.')}
            </div>
            ${caseRawComplaint(c) && caseRawComplaint(c) !== caseNarrative(c) ? `<details class="complaint-source-text"><summary>Original words or voice transcript</summary><div class="investigator-narrative">${escapeHtml(caseRawComplaint(c))}</div></details>` : ''}
          </div>

          <div class="investigator-detail-card">
            <h4>Suspect or recipient details</h4>
            ${suspectsHtml}
          </div>

          <div class="investigator-detail-card">
            <h4>Evidence files</h4>
            ${evidenceHtml}
          </div>

          <div class="investigator-detail-card"><h4>Evidence cross-check</h4>${reconciliationHtml}</div>

          <div class="investigator-detail-card"><h4>Similar records to verify manually</h4><div id="case-links-${escapeHtml(safeRef)}" class="case-links-status">Checking the local review queue…</div></div>

          <div class="investigator-detail-card case-review-controls">
            <h4>Review decision</h4>
            <label>Reviewer name or initials<input id="reviewer-${escapeHtml(safeRef)}" maxlength="20" autocomplete="off" placeholder="Enter your name or initials"></label>
            <label>Reason for this decision<textarea id="review-note-${escapeHtml(safeRef)}" maxlength="1000" rows="3" placeholder="Record what you checked and why you confirmed or changed the suggested type."></textarea></label>
            <div class="case-actions-row">
              <button type="button" class="btn-table-action case-action-confirm" data-case-action="confirm">
                ✓ Confirm suggested type
              </button>
              <button type="button" class="btn-table-action case-action-bank" data-case-action="bank-notice">
                🏦 Draft bank request
              </button>
              <button type="button" class="btn-table-action case-action-records" data-case-action="telecom-notice">
                📱 Draft phone-record request
              </button>
            </div>
            <label>Corrected incident type<select id="reclass-category-${escapeHtml(safeRef)}" aria-label="Select corrected incident type">${categoryOptions.map(category => `<option value="${escapeHtml(category)}" ${category === c.classification?.sub_category ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select></label>
            <button type="button" class="btn-table-action" data-case-action="reclassify">Save corrected type</button>
          </div>

          <div class="investigator-detail-card">
            <h4>Workflow and assignment</h4>
            <form class="workflow-form" data-case-workflow="${escapeHtml(c.reference)}">
              <label>Status<select name="status" required>
                ${['RECEIVED - AWAITING REVIEW','IN REVIEW','AWAITING INFORMATION','REFERRED FOR FOLLOW-UP','REVIEW COMPLETE','CATEGORY REVIEWED','CONFIRMED BY OFFICER','RECLASSIFIED BY OFFICER','PENDING OFFICER REVIEW'].map(s => `<option value="${s}" ${(c.status || 'RECEIVED - AWAITING REVIEW') === s ? 'selected' : ''}>${escapeHtml(formatCaseStatus(s))}</option>`).join('')}
              </select></label>
              <label>Assign to<input name="assigned_to" value="${escapeHtml(c.assigned_to || '')}" autocomplete="off" placeholder="Investigator name or team"></label>
              <label>Updated by<input name="reviewer" required maxlength="20" autocomplete="off" placeholder="Your name or initials"></label>
              <label>Next action or note<textarea name="note" required maxlength="1000" rows="2" placeholder="What should happen next? Add a brief reason."></textarea></label>
              <button class="btn-primary-action" type="submit">Save workflow update</button>
            </form>
            ${(c._activity_log || []).length ? `<details><summary>Workflow history (${c._activity_log.length})</summary>${c._activity_log.map(a => `<p><strong>${escapeHtml(a.at || '')} · ${escapeHtml(a.actor || 'System')}</strong><br>${escapeHtml(a.details || a.action || '')}</p>`).join('')}</details>` : ''}
          </div>
        </div>
      </div>
    `;

    modalFooter.innerHTML = `
      <div class="case-modal-footer">
        <span class="case-modal-status">Current status: <strong>${escapeHtml(formatCaseStatus(c.status))}</strong></span>
        <div class="case-modal-actions">
          <a href="${pdfUrl}" target="_blank" rel="noopener" class="btn-download-pdf-clean">
            📄 Download complaint draft
          </a>
          <button type="button" class="btn-inspect-case" data-close-case-modal>
            Close
          </button>
        </div>
      </div>
    `;
    modalFooter.querySelector('[data-close-case-modal]')?.addEventListener('click', () => { modal.style.display = 'none'; });
    modalBody.querySelectorAll('[data-case-action]').forEach(button => button.addEventListener('click', () => {
      const action = button.dataset.caseAction;
      if (action === 'confirm') adjudicateCase(c.reference, 'CONFIRM', '', safeRef);
      if (action === 'reclassify') adjudicateCase(c.reference, 'RECLASSIFY', document.getElementById(`reclass-category-${safeRef}`)?.value || '', safeRef);
      if (action === 'bank-notice') generateStatutoryNotice(c.reference, 'BANK_FREEZE_NOTICE');
      if (action === 'telecom-notice') generateStatutoryNotice(c.reference, 'TELECOM_CDR_NOTICE');
    }));
    modalBody.querySelector('[data-case-workflow]')?.addEventListener('submit', event => saveCaseWorkflow(event, c.reference));
    loadCaseLinks(c.reference, safeRef);

  } catch (err) {
    modalBody.innerHTML = `<div style="text-align:center; padding: 2rem; color: #dc2626;">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadCaseLinks(caseRef, safeRef) {
  const target = document.getElementById(`case-links-${safeRef}`);
  if (!target) return;
  try {
    const response = await fetch('/api/cases/syndicate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reference: caseRef }) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.detail || data.error || 'Related records are unavailable.');
    const linked = data.links?.linked_cases || [];
    target.replaceChildren();
    if (!linked.length) { target.textContent = 'No shared indicators were found in the current local queue.'; return; }
    const note = document.createElement('p'); note.textContent = `${linked.length} possible related record(s). A shared indicator is a lead only; check each case independently.`; target.appendChild(note);
    linked.forEach(item => {
      const row = document.createElement('p');
      row.textContent = `${item.reference || 'Case'} · ${item.sub_category || 'Unclassified'} · shared: ${(item.shared_identifiers || []).join(', ') || 'indicator match'}`;
      target.appendChild(row);
    });
  } catch (error) { target.textContent = `Related-record check unavailable: ${error.message}`; }
}

async function adjudicateCase(caseRef, action, newCategory = '', safeRef = '') {
  const reviewer = document.getElementById(`reviewer-${safeRef}`)?.value.trim() || '';
  const note = document.getElementById(`review-note-${safeRef}`)?.value.trim() || '';
  if (!reviewer || !note) { showToast('Enter reviewer initials and a short review note before saving this action.'); return; }
  try {
    const res = await fetch('/api/cases/adjudicate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reference: caseRef,
        action: action,
        new_category: newCategory || null,
        reviewer,
        officer_note: note
      })
    });
    if (!res.ok) throw new Error("Could not save the review");
    showToast(`Review saved for ${caseRef}.`);
    inspectCaseDetail(caseRef);
    loadDashboardCases();
  } catch (err) {
    showToast("Could not save review: " + err.message);
  }
}

async function saveCaseWorkflow(event, caseRef) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form).entries());
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const response = await fetch('/api/cases/workflow', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reference: caseRef, ...values }) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.detail || data.error || 'Could not save workflow update.');
    showToast('Workflow update saved.');
    await loadDashboardCases();
    await inspectCaseDetail(caseRef);
  } catch (error) { showToast(error.message); submit.disabled = false; }
}

async function generateStatutoryNotice(caseRef, docType) {
  showToast("Preparing document draft...");
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
    showToast("Document draft downloaded.");
  } catch (err) {
    showToast("Notice generation error: " + err.message);
  }
}
