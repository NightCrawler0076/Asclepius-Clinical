// ============================================================
// Asclepius Clinical Assistant — Unified Consultation Controller
// Supports: Live Microphone, Speaker Loopback, File Upload, Reset
// Enforces: Active Doctor and Patient selection before recording
// ============================================================

let currentConsultationId = null;
let currentPrescriptionId = null;
let currentPrescription = null;

// ── UI Helpers ─────────────────────────────────────────────
function setStatus(statusBoxElement, message, statusType) {
  if (!message) {
    statusBoxElement.style.display = 'none';
    statusBoxElement.className = 'status-box';
    statusBoxElement.textContent = '';
    return;
  }
  // Clear any inline display:none left by a previous setStatus('', '') call.
  // Inline styles beat CSS classes, so without this the box stays invisible.
  statusBoxElement.style.display = '';
  statusBoxElement.textContent = message;
  statusBoxElement.className = `status-box active ${statusType || ''}`;
}

async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return { res, data, response: res, responseData: data };
}

// ── Tab Switching ──────────────────────────────────────────
const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanels = document.querySelectorAll('.tab-panel');

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    tabPanels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + btn.dataset.tab);
    if (panel) panel.classList.add('active');
  });
});

// ============================================================
// 1. DEVICE ENUMERATION & SETUP
// ============================================================

const micDeviceSelect = document.getElementById('mic-device-select');
const systemDeviceSelect = document.getElementById('system-device-select');
const modelSizeSelect = document.getElementById('model-size-select');

async function loadAudioDevices() {
  try {
    const micDevices = await apiGet('/api/input-devices');
    micDeviceSelect.innerHTML = '<option value="">Default Microphone</option>';
    micDevices.forEach(device => {
      const optionElement = document.createElement('option');
      optionElement.value = device.id;
      optionElement.textContent = `${device.name}${device.default ? ' [DEFAULT]' : ''}`;
      if (device.default) optionElement.selected = true;
      micDeviceSelect.appendChild(optionElement);
    });
  } catch (error) {
    console.error('Error loading mic devices:', error);
  }

  try {
    const systemDevices = await apiGet('/api/output-devices');
    systemDeviceSelect.innerHTML = '<option value="">Default Speaker Output</option>';
    systemDevices.forEach(device => {
      const optionElement = document.createElement('option');
      optionElement.value = device.name;
      optionElement.textContent = device.name + (device.default ? ' [DEFAULT]' : '');
      if (device.default) optionElement.selected = true;
      systemDeviceSelect.appendChild(optionElement);
    });
  } catch (error) {
    console.warn('Error loading speaker devices:', error);
  }
}

// ============================================================
// 2. DOCTOR & PATIENT MANAGEMENT
// ============================================================

const doctorSelect = document.getElementById('doctor-select');
const patientSelect = document.getElementById('patient-select');

async function loadDoctors() {
  const doctorsList = await apiGet('/api/doctors');
  doctorSelect.innerHTML = '<option value="">Select physician...</option>';
  doctorsList.forEach(doctor => {
    const optionElement = document.createElement('option');
    optionElement.value = doctor.id;
    optionElement.textContent = `${doctor.name}${doctor.specialty ? ' (' + doctor.specialty + ')' : ''}`;
    doctorSelect.appendChild(optionElement);
  });
}

async function loadPatients() {
  const patientsList = await apiGet('/api/patients');
  patientSelect.innerHTML = '<option value="">Select patient...</option>';
  patientsList.forEach(patient => {
    const optionElement = document.createElement('option');
    optionElement.value = patient.id;
    optionElement.textContent = `${patient.name}${patient.age ? ', ' + patient.age + ' yrs' : ''}${patient.sex ? ' (' + patient.sex + ')' : ''}`;
    patientSelect.appendChild(optionElement);
  });
}

// Inline Doctor Add
const newDocPanel = document.getElementById('new-doctor-panel');
document.getElementById('toggle-new-doctor-btn').addEventListener('click', () => {
  newDocPanel.style.display = newDocPanel.style.display === 'none' ? 'block' : 'none';
});
document.getElementById('cancel-doctor-btn').addEventListener('click', () => {
  newDocPanel.style.display = 'none';
});
document.getElementById('save-doctor-btn').addEventListener('click', async () => {
  const name = document.getElementById('new-doc-name').value.trim();
  if (!name) {
    setStatus(audioStatusBox, 'Doctor name is required.', 'error');
    return;
  }
  const { data } = await apiPost('/api/doctors', {
    name,
    specialty: document.getElementById('new-doc-specialty').value,
    clinic_name: document.getElementById('new-doc-clinic').value,
    phone: document.getElementById('new-doc-phone').value,
  });
  document.getElementById('new-doc-name').value = '';
  document.getElementById('new-doc-specialty').value = '';
  document.getElementById('new-doc-clinic').value = '';
  document.getElementById('new-doc-phone').value = '';
  newDocPanel.style.display = 'none';
  await loadDoctors();
  doctorSelect.value = data.id;
  setStatus(audioStatusBox, '', '');
});

// Inline Patient Add
const newPatPanel = document.getElementById('new-patient-panel');
document.getElementById('toggle-new-patient-btn').addEventListener('click', () => {
  newPatPanel.style.display = newPatPanel.style.display === 'none' ? 'block' : 'none';
});
document.getElementById('cancel-patient-btn').addEventListener('click', () => {
  newPatPanel.style.display = 'none';
});
document.getElementById('save-patient-btn').addEventListener('click', async () => {
  const name = document.getElementById('new-pat-name').value.trim();
  if (!name) {
    setStatus(audioStatusBox, 'Patient name is required.', 'error');
    return;
  }
  const age = document.getElementById('new-pat-age').value;
  const { data } = await apiPost('/api/patients', {
    name,
    age: age ? parseInt(age) : null,
    sex: document.getElementById('new-pat-sex').value,
  });
  document.getElementById('new-pat-name').value = '';
  document.getElementById('new-pat-age').value = '';
  document.getElementById('new-pat-sex').value = '';
  newPatPanel.style.display = 'none';
  await loadPatients();
  patientSelect.value = data.id;
  setStatus(audioStatusBox, '', '');
});

// Clear warning whenever selections change
doctorSelect.addEventListener('change', () => {
  if (doctorSelect.value && patientSelect.value) {
    setStatus(audioStatusBox, '', '');
  }
});
patientSelect.addEventListener('change', () => {
  if (doctorSelect.value && patientSelect.value) {
    setStatus(audioStatusBox, '', '');
  }
});

// ============================================================
// 3. CONSULTATION ENFORCEMENT
// ============================================================

function validateClinicalContext() {
  const selectedDoctorId = doctorSelect.value;
  const selectedPatientId = patientSelect.value;

  if (!selectedDoctorId || !selectedPatientId) {
    let missingEntities = [];
    if (!selectedDoctorId) missingEntities.push('Physician');
    if (!selectedPatientId) missingEntities.push('Patient');
    setStatus(
      audioStatusBox,
      `Please select or register both a ${missingEntities.join(' and ')} before starting audio capture.`,
      'error'
    );
    // Smooth scroll to clinical context card
    const allCards = document.querySelectorAll('.card');
    if (allCards[1]) allCards[1].scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
  }
  return true;
}

async function ensureConsultationSession() {
  if (currentConsultationId) return currentConsultationId;

  const selectedDoctorId = doctorSelect.value;
  const selectedPatientId = patientSelect.value;

  if (!selectedDoctorId || !selectedPatientId) {
    throw new Error('Both Physician and Patient must be selected.');
  }

  const { response, responseData } = await apiPost('/api/consultations', {
    doctor_id: selectedDoctorId,
    patient_id: selectedPatientId,
  });

  if (!response.ok) throw new Error(responseData.error || 'Failed to create consultation session.');

  currentConsultationId = responseData.id;
  return currentConsultationId;
}

// ============================================================
// 4. AUDIO CAPTURE & RECOGNITION (MIC / SYSTEM / FILE)
// ============================================================

const audioStatusBox = document.getElementById('audio-status-box');
const audioPlayback = document.getElementById('audio-playback');
const transcriptSection = document.getElementById('transcript-section');
const transcriptText = document.getElementById('transcript-text');

async function handleTranscriptionOutput(text, audioUrl) {
  if (audioUrl) {
    audioPlayback.src = audioUrl + '?t=' + Date.now();
    audioPlayback.style.display = 'block';
  }

  if (text) {
    transcriptText.value = text;
    transcriptSection.style.display = 'block';

    const consId = await ensureConsultationSession();
    const model = modelSizeSelect.value;

    await apiPost(`/api/consultations/${consId}/transcript`, {
      text,
      model_used: model,
    });

    // Automatically trigger prescription extraction
    await triggerPrescriptionGeneration();
  } else {
    setStatus(audioStatusBox, 'Transcription complete: No speech detected.', 'warning');
  }
}

// ── Mic Capture ──
const micStartBtn = document.getElementById('mic-start-btn');
const micStopBtn = document.getElementById('mic-stop-btn');

micStartBtn.addEventListener('click', async () => {
  if (!validateClinicalContext()) return;

  transcriptSection.style.display = 'none';
  audioPlayback.style.display = 'none';
  setStatus(audioStatusBox, '', '');

  const devVal = micDeviceSelect.value;
  const deviceId = (devVal !== '' && !isNaN(parseInt(devVal, 10))) ? parseInt(devVal, 10) : null;
  try {
    const { res, data } = await apiPost('/api/mic/start', { device_id: deviceId });
    if (!res.ok) throw new Error(data.error);

    micStartBtn.disabled = true;
    micStopBtn.disabled = false;
    setStatus(audioStatusBox, 'Recording from microphone... Speak now.', 'info');
  } catch (e) {
    setStatus(audioStatusBox, 'Failed to start microphone: ' + e.message, 'error');
  }
});

micStopBtn.addEventListener('click', async () => {
  micStopBtn.disabled = true;
  setStatus(audioStatusBox, 'Processing & transcribing audio with Whisper...', 'info');

  try {
    const model = modelSizeSelect.value;
    const { res, data } = await apiPost('/api/mic/stop', { model_size: model });
    if (!res.ok) throw new Error(data.error);

    setStatus(audioStatusBox, '', '');
    await handleTranscriptionOutput(data.text, data.audio_url);
  } catch (e) {
    setStatus(audioStatusBox, e.message, 'error');
  } finally {
    micStartBtn.disabled = false;
  }
});

// ── System Audio Capture (Loopback) ──
const systemStartBtn = document.getElementById('system-start-btn');
const systemStopBtn = document.getElementById('system-stop-btn');

systemStartBtn.addEventListener('click', async () => {
  if (!validateClinicalContext()) return;

  transcriptSection.style.display = 'none';
  audioPlayback.style.display = 'none';
  setStatus(audioStatusBox, '', '');

  const devName = systemDeviceSelect.value;
  try {
    const { res, data } = await apiPost('/api/system/start', { device_name: devName });
    if (!res.ok) throw new Error(data.error);

    systemStartBtn.disabled = true;
    systemStopBtn.disabled = false;
    setStatus(audioStatusBox, '', '');
  } catch (e) {
    setStatus(audioStatusBox, 'Failed to start speaker capture: ' + e.message, 'error');
  }
});

systemStopBtn.addEventListener('click', async () => {
  systemStopBtn.disabled = true;
  setStatus(audioStatusBox, '', '');

  try {
    const model = modelSizeSelect.value;
    const { res, data } = await apiPost('/api/system/stop', { model_size: model });
    if (!res.ok) throw new Error(data.error);

    setStatus(audioStatusBox, '', '');
    await handleTranscriptionOutput(data.text, data.audio_url);
  } catch (e) {
    setStatus(audioStatusBox, e.message, 'error');
  } finally {
    systemStartBtn.disabled = false;
  }
});

// ── File Upload ──
const fileUploadInput = document.getElementById('file-upload-input');
const fileTranscribeBtn = document.getElementById('file-transcribe-btn');

fileUploadInput.addEventListener('change', () => {
  transcriptSection.style.display = 'none';
  setStatus(audioStatusBox, '', '');
  if (fileUploadInput.files.length > 0) {
    const file = fileUploadInput.files[0];
    audioPlayback.src = URL.createObjectURL(file);
    audioPlayback.style.display = 'block';
    fileTranscribeBtn.disabled = false;
  } else {
    audioPlayback.style.display = 'none';
    fileTranscribeBtn.disabled = true;
  }
});

fileTranscribeBtn.addEventListener('click', async () => {
  if (!validateClinicalContext()) return;
  if (fileUploadInput.files.length === 0) return;

  const file = fileUploadInput.files[0];
  const model = modelSizeSelect.value;

  fileTranscribeBtn.disabled = true;
  setStatus(audioStatusBox, '', '');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('model_size', model);

  try {
    const res = await fetch('/api/file/transcribe', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload transcription failed');

    setStatus(audioStatusBox, '', '');
    await handleTranscriptionOutput(data.text, null);
  } catch (e) {
    setStatus(audioStatusBox, e.message, 'error');
  } finally {
    fileTranscribeBtn.disabled = false;
  }
});

// ============================================================
// 5. CLINICAL EXTRACTION & PRESCRIPTION REVIEW
// ============================================================

const genPrescriptionBtn = document.getElementById('generate-prescription-btn');
const rxCard = document.getElementById('prescription-card');
const rxStatusBox = document.getElementById('rx-status-box');

async function triggerPrescriptionGeneration() {
  const text = transcriptText.value.trim();
  if (!text) return;

  const consId = await ensureConsultationSession();

  // NOTE: transcript was already saved in handleTranscriptionOutput;
  // do NOT re-POST here — it would overwrite model_used/language with blanks.

  setStatus(audioStatusBox, '', '');

  try {
    const selectedLlm = llmModelSelect ? llmModelSelect.value : null;
    const { res, data } = await apiPost(`/api/consultations/${consId}/prescription/generate`, {
      llm_model: selectedLlm,
    });
    if (!res.ok) throw new Error(data.error);

    currentPrescriptionId = data.prescription_id;
    currentPrescription = data.prescription;

    renderPrescription(data.prescription, data.warnings);
    rxCard.style.display = 'block';
    setStatus(audioStatusBox, '', '');

    rxCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    setStatus(audioStatusBox, 'Extraction error: ' + e.message, 'error');
  }
}

genPrescriptionBtn.addEventListener('click', triggerPrescriptionGeneration);

const downloadPdfBtn = document.getElementById('rx-download-pdf-btn');

downloadPdfBtn.addEventListener('click', () => {
  if (!currentPrescriptionId) return;
  window.open(`/api/prescriptions/${currentPrescriptionId}/pdf`, '_blank');
});

function updatePdfDownloadButton() {
  if (currentPrescriptionId) {
    downloadPdfBtn.style.display = 'inline-flex';
  } else {
    downloadPdfBtn.style.display = 'none';
  }
}

function renderPrescription(rx, warnings) {
  updatePdfDownloadButton();
  const warnContainer = document.getElementById('prescription-warnings-container');
  warnContainer.innerHTML = '';
  if (warnings && warnings.length > 0) {
    warnings.forEach(w => {
      const el = document.createElement('div');
      el.className = 'status-box active busy';
      el.style.marginBottom = '16px';
      el.textContent = `Notice: ${w.message}`;
      warnContainer.appendChild(el);
    });
  }

  const pat = rx.patient || {};
  document.getElementById('rx-pat-name').value = pat.name || '';
  document.getElementById('rx-pat-age').value = pat.age || '';
  document.getElementById('rx-pat-sex').value = pat.sex || '';

  const complaints = rx.complaints || [];
  const complaintsContainer = document.getElementById('rx-complaints-tags');
  complaintsContainer.innerHTML = '';
  complaints.forEach((c, idx) => {
    const tag = document.createElement('span');
    tag.className = 'clinical-tag symptom';
    tag.textContent = c.name || '';
    tag.style.cursor = 'pointer';
    tag.title = 'Click to remove';
    tag.addEventListener('click', () => {
      rx.complaints.splice(idx, 1);
      renderPrescription(currentPrescription, []);
    });
    complaintsContainer.appendChild(tag);
  });
  const cBadge = document.getElementById('complaints-count-badge');
  if (cBadge) cBadge.textContent = `${complaints.length} item${complaints.length === 1 ? '' : 's'}`;

  const diagnoses = rx.diagnosis || [];
  const diagnosisContainer = document.getElementById('rx-diagnosis-tags');
  diagnosisContainer.innerHTML = '';
  diagnoses.forEach((d, idx) => {
    const tag = document.createElement('span');
    tag.className = 'clinical-tag diagnosis';
    tag.textContent = d;
    tag.style.cursor = 'pointer';
    tag.title = 'Click to remove';
    tag.addEventListener('click', () => {
      rx.diagnosis.splice(idx, 1);
      renderPrescription(currentPrescription, []);
    });
    diagnosisContainer.appendChild(tag);
  });
  const dBadge = document.getElementById('diagnosis-count-badge');
  if (dBadge) dBadge.textContent = `${diagnoses.length} item${diagnoses.length === 1 ? '' : 's'}`;

  const meds = rx.medications || [];
  const tbody = document.getElementById('rx-meds-tbody');
  tbody.innerHTML = '';
  meds.forEach((med, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input value="${med.name || ''}" data-field="name" data-idx="${i}" placeholder="Drug name"></td>
      <td><input value="${med.dose || ''}" data-field="dose" data-idx="${i}" placeholder="e.g. 500mg"></td>
      <td><input value="${med.frequency || ''}" data-field="frequency" data-idx="${i}" placeholder="e.g. 2x/day"></td>
      <td><input value="${med.duration || ''}" data-field="duration" data-idx="${i}" placeholder="e.g. 5 days"></td>
      <td style="text-align: center;"><button class="btn btn-danger-ghost btn-sm rx-del-med-btn" data-idx="${i}" title="Remove medication" style="font-size: 16px;">&times;</button></td>
    `;
    tbody.appendChild(tr);
  });
  const mBadge = document.getElementById('meds-count-badge');
  if (mBadge) mBadge.textContent = `${meds.length} Rx`;

  tbody.querySelectorAll('.rx-del-med-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx, 10);
      currentPrescription.medications.splice(idx, 1);
      renderPrescription(currentPrescription, []);
    });
  });

  const investigations = rx.investigations || [];
  const invContainer = document.getElementById('rx-investigations-tags');
  invContainer.innerHTML = '';
  investigations.forEach((inv, idx) => {
    const tag = document.createElement('span');
    tag.className = 'clinical-tag investigation';
    tag.textContent = inv;
    tag.style.cursor = 'pointer';
    tag.title = 'Click to remove';
    tag.addEventListener('click', () => {
      rx.investigations.splice(idx, 1);
      renderPrescription(currentPrescription, []);
    });
    invContainer.appendChild(tag);
  });
  const iBadge = document.getElementById('inv-count-badge');
  if (iBadge) iBadge.textContent = `${investigations.length} order${investigations.length === 1 ? '' : 's'}`;

  document.getElementById('rx-advice-input').value = (rx.advice || []).join('\n');
  document.getElementById('rx-followup-input').value = rx.follow_up || '';
  document.getElementById('rx-notes-input').value = rx.doctor_notes || '';
}

document.getElementById('rx-add-med-btn').addEventListener('click', () => {
  if (!currentPrescription) return;
  currentPrescription.medications.push({
    name: '', dose: '', route: '', frequency: '', duration: '', instructions: ''
  });
  renderPrescription(currentPrescription, []);
});

const addComplaintInput = document.getElementById('rx-add-complaint-input');
if (addComplaintInput) {
  addComplaintInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = e.target.value.trim();
      if (val && currentPrescription) {
        if (!currentPrescription.complaints) currentPrescription.complaints = [];
        currentPrescription.complaints.push({ name: val, duration: '' });
        e.target.value = '';
        renderPrescription(currentPrescription, []);
      }
    }
  });
}

const addInvInput = document.getElementById('rx-add-investigation-input');
if (addInvInput) {
  addInvInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = e.target.value.trim();
      if (val && currentPrescription) {
        if (!currentPrescription.investigations) currentPrescription.investigations = [];
        currentPrescription.investigations.push(val);
        e.target.value = '';
        renderPrescription(currentPrescription, []);
      }
    }
  });
}

// Quick chip handlers for follow-up
document.querySelectorAll('.quick-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const val = chip.dataset.val;
    const input = document.getElementById('rx-followup-input');
    if (input && val) {
      input.value = val;
      if (currentPrescription) currentPrescription.follow_up = val;
    }
  });
});

document.getElementById('rx-add-diagnosis-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const val = e.target.value.trim();
    if (val && currentPrescription) {
      if (!currentPrescription.diagnosis) currentPrescription.diagnosis = [];
      currentPrescription.diagnosis.push(val);
      e.target.value = '';
      renderPrescription(currentPrescription, []);
    }
  }
});

function syncEditsToPrescriptionObject() {
  if (!currentPrescription) return;

  currentPrescription.patient = {
    name: document.getElementById('rx-pat-name').value,
    age: parseInt(document.getElementById('rx-pat-age').value, 10) || null,
    sex: document.getElementById('rx-pat-sex').value,
    patient_id: currentPrescription.patient?.patient_id || '',
  };

  const rows = document.getElementById('rx-meds-tbody').querySelectorAll('tr');
  currentPrescription.medications = [];
  rows.forEach(tr => {
    const inputs = tr.querySelectorAll('input');
    currentPrescription.medications.push({
      name: inputs[0].value,
      dose: inputs[1].value,
      frequency: inputs[2].value,
      duration: inputs[3].value,
      route: '',
      instructions: '',
    });
  });

  currentPrescription.advice = document.getElementById('rx-advice-input').value
    .split('\n').map(s => s.trim()).filter(Boolean);
  currentPrescription.follow_up = document.getElementById('rx-followup-input').value;
  currentPrescription.doctor_notes = document.getElementById('rx-notes-input').value;
}

document.getElementById('rx-save-draft-btn').addEventListener('click', async () => {
  syncEditsToPrescriptionObject();
  try {
    const res = await fetch(`/api/prescriptions/${currentPrescriptionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: currentPrescription, status: 'draft' }),
    });
    if (!res.ok) throw new Error('Save draft failed');
    setStatus(rxStatusBox, 'Prescription draft saved successfully.', 'success');
    updatePdfDownloadButton();
    await loadPrescriptionHistory();
  } catch (e) {
    setStatus(rxStatusBox, e.message, 'error');
  }
});

document.getElementById('rx-confirm-btn').addEventListener('click', async () => {
  syncEditsToPrescriptionObject();
  if (!confirm('Authorize and confirm this prescription?')) return;

  try {
    await fetch(`/api/prescriptions/${currentPrescriptionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: currentPrescription, status: 'confirmed' }),
    });

    const { res, data } = await apiPost(`/api/prescriptions/${currentPrescriptionId}/confirm`, {});
    if (!res.ok) throw new Error(data.error);

    setStatus(rxStatusBox, 'Prescription authorized and locked as confirmed.', 'success');
    document.getElementById('rx-confirm-btn').disabled = true;
    updatePdfDownloadButton();
    await loadPrescriptionHistory();
  } catch (e) {
    setStatus(rxStatusBox, e.message, 'error');
  }
});

// ============================================================
// 6. SAVED PRESCRIPTIONS HISTORY & DELETION
// ============================================================

const historyTbody = document.getElementById('history-tbody');
const historyCountPill = document.getElementById('history-count-pill');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');

async function loadPrescriptionHistory() {
  try {
    const prescriptions = await apiGet('/api/prescriptions');
    historyCountPill.textContent = `${prescriptions.length} Record${prescriptions.length === 1 ? '' : 's'}`;

    if (!prescriptions || prescriptions.length === 0) {
      historyTbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty-state">No saved prescriptions found yet. Record or generate a prescription above.</td>
        </tr>
      `;
      return;
    }

    historyTbody.innerHTML = '';
    prescriptions.forEach(prescriptionItem => {
      const tableRow = document.createElement('tr');
      const prescriptionData = prescriptionItem.data || {};
      const patientDisplayName = prescriptionItem.patient_name || prescriptionData.patient?.name || '—';
      const patientSummary = `${patientDisplayName}${prescriptionItem.patient_age ? ' (' + prescriptionItem.patient_age + (prescriptionItem.patient_sex ? ', ' + prescriptionItem.patient_sex : '') + ')' : ''}`;
      const doctorSummary = prescriptionItem.doctor_name ? `${prescriptionItem.doctor_name}${prescriptionItem.doctor_specialty ? ' (' + prescriptionItem.doctor_specialty + ')' : ''}` : '—';
      
      const prescribedMedNames = (prescriptionData.medications || []).map(med => med.name).filter(Boolean);
      const diagnosisNames = prescriptionData.diagnosis || [];
      const clinicalSummary = prescribedMedNames.length > 0 
        ? `${prescribedMedNames.slice(0, 3).join(', ')}${prescribedMedNames.length > 3 ? ' +' + (prescribedMedNames.length - 3) + ' more' : ''}`
        : (diagnosisNames.join(', ') || '—');

      const formattedDate = prescriptionItem.created_at || '—';
      const statusBadgeClass = prescriptionItem.status === 'confirmed' ? 'confirmed' : '';
      const statusText = (prescriptionItem.status || 'draft').toUpperCase();

      tableRow.innerHTML = `
        <td style="font-size: 12px; color: var(--text-secondary);">${formattedDate}</td>
        <td><strong>${patientSummary}</strong></td>
        <td style="color: var(--text-secondary);">${doctorSummary}</td>
        <td style="font-size: 12px; color: var(--text-muted);">${clinicalSummary}</td>
        <td><span class="badge-status ${statusBadgeClass}">${statusText}</span></td>
        <td style="text-align: right; white-space: nowrap;">
          <div style="display: inline-flex; gap: 6px; align-items: center;">
            <a href="/prescription/${prescriptionItem.consultation_id}" class="btn btn-outline btn-sm" target="_blank" title="View formatted prescription page">View</a>
            <a href="/api/prescriptions/${prescriptionItem.id}/pdf" class="btn btn-secondary btn-sm" target="_blank" title="Download PDF document">PDF</a>
            <button class="btn btn-danger-ghost btn-sm rx-history-del-btn" data-id="${prescriptionItem.id}" data-patient="${patientDisplayName}" title="Delete prescription record">Delete</button>
          </div>
        </td>
      `;
      historyTbody.appendChild(tableRow);
    });

    // Attach delete listeners
    historyTbody.querySelectorAll('.rx-history-del-btn').forEach(deleteButton => {
      deleteButton.addEventListener('click', async () => {
        const recordId = deleteButton.dataset.id;
        const patientName = deleteButton.dataset.patient;
        if (!confirm(`Are you sure you want to permanently delete Prescription #${recordId} for ${patientName}?`)) return;

        try {
          const deleteResponse = await fetch(`/api/prescriptions/${recordId}`, { method: 'DELETE' });
          if (!deleteResponse.ok) {
            const errorData = await deleteResponse.json();
            throw new Error(errorData.error || 'Delete failed');
          }
          await loadPrescriptionHistory();
        } catch (error) {
          alert('Could not delete prescription: ' + error.message);
        }
      });
    });

  } catch (e) {
    console.error('Error loading prescription history:', e);
    historyTbody.innerHTML = `
      <tr>
        <td colspan="6" class="empty-state" style="color: var(--error-text);">Failed to load history: ${e.message}</td>
      </tr>
    `;
  }
}

refreshHistoryBtn.addEventListener('click', loadPrescriptionHistory);

// ============================================================
// 7. GLOBAL RESET TO INITIAL STATE
// ============================================================

function resetSession() {
  currentConsultationId = null;
  currentPrescriptionId = null;
  currentPrescription = null;

  audioPlayback.pause();
  audioPlayback.src = '';
  audioPlayback.style.display = 'none';

  micStartBtn.disabled = false;
  micStopBtn.disabled = true;

  systemStartBtn.disabled = false;
  systemStopBtn.disabled = true;

  fileUploadInput.value = '';
  fileTranscribeBtn.disabled = true;

  setStatus(audioStatusBox, '', '');
  setStatus(rxStatusBox, '', '');

  transcriptText.value = '';
  transcriptSection.style.display = 'none';
  rxCard.style.display = 'none';
  downloadPdfBtn.style.display = 'none';

  document.getElementById('rx-pat-name').value = '';
  document.getElementById('rx-pat-age').value = '';
  document.getElementById('rx-pat-sex').value = '';
  document.getElementById('rx-complaints-tags').innerHTML = '';
  document.getElementById('rx-diagnosis-tags').innerHTML = '';
  document.getElementById('rx-meds-tbody').innerHTML = '';
  document.getElementById('rx-investigations-tags').innerHTML = '';
  document.getElementById('rx-advice-input').value = '';
  document.getElementById('rx-followup-input').value = '';
  document.getElementById('rx-notes-input').value = '';
  document.getElementById('prescription-warnings-container').innerHTML = '';
  document.getElementById('rx-confirm-btn').disabled = false;

  tabButtons.forEach(b => b.classList.remove('active'));
  tabPanels.forEach(p => p.classList.remove('active'));
  tabButtons[0].classList.add('active');
  document.getElementById('tab-mic').classList.add('active');

  // Re-enumerate and refresh all input & output audio capture devices
  loadAudioDevices();
  loadDoctors();
  loadPatients();
  loadPrescriptionHistory();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.getElementById('global-reset-btn').addEventListener('click', resetSession);

const llmModelSelect = document.getElementById('llm-model-select');

// ============================================================
// INITIALIZATION
// ============================================================

loadAudioDevices();
loadDoctors();
loadPatients();
loadPrescriptionHistory();
initLlmSelector();

// ── LLM Status & Selector Management ─────────────────────────
function updateLlmStatusDisplay(status) {
  const pill = document.getElementById('llm-status-pill');
  const text = document.getElementById('llm-status-text');
  const dot = pill ? pill.querySelector('.status-dot') : null;
  if (!pill || !text || !dot || !status) return;

  if (status.active) {
    dot.classList.remove('status-inactive');
    dot.classList.add('status-active');
    text.textContent = status.model_loaded ? `LLM: ${status.active_model_name || 'Active'}` : `LLM: Ready`;
    pill.title = `${status.model_name || status.active_model_name} — refinement enabled`;
  } else {
    dot.classList.remove('status-active');
    dot.classList.add('status-inactive');
    if (!status.enabled) {
      text.textContent = 'LLM: Disabled';
      pill.title = 'LLM refinement is disabled in config';
    } else if (!status.model_exists) {
      text.textContent = 'LLM: No Model';
      pill.title = 'Model file not found on disk';
    } else if (!status.lib_installed) {
      text.textContent = 'LLM: No Lib';
      pill.title = 'llama-cpp-python not installed';
    } else {
      text.textContent = 'LLM: Inactive';
    }
  }
}

async function initLlmSelector() {
  if (!llmModelSelect) {
    checkLlmStatus();
    return;
  }

  try {
    const [models, status] = await Promise.all([
      apiGet('/api/llm/models'),
      apiGet('/api/llm/status'),
    ]);

    llmModelSelect.innerHTML = '';
    if (Array.isArray(models) && models.length > 0) {
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        const statusLabel = m.file_exists ? `(~${m.ram_mb}MB)` : '(Not Downloaded)';
        opt.textContent = `${m.name} ${statusLabel}`;
        if (m.is_active) opt.selected = true;
        llmModelSelect.appendChild(opt);
      });
    }

    const disabledOpt = document.createElement('option');
    disabledOpt.value = 'disabled';
    disabledOpt.textContent = 'Disabled (Regex only)';
    if (status && !status.enabled) disabledOpt.selected = true;
    llmModelSelect.appendChild(disabledOpt);

    updateLlmStatusDisplay(status);
  } catch (err) {
    console.warn('Error initializing LLM models selector:', err);
    checkLlmStatus();
  }

  llmModelSelect.addEventListener('change', async () => {
    const selectedKey = llmModelSelect.value;
    if (selectedKey === 'disabled') {
      const pill = document.getElementById('llm-status-pill');
      const text = document.getElementById('llm-status-text');
      const dot = pill ? pill.querySelector('.status-dot') : null;
      if (dot) {
        dot.classList.remove('status-active');
        dot.classList.add('status-inactive');
      }
      if (text) text.textContent = 'LLM: Disabled';
      if (pill) pill.title = 'LLM refinement disabled by user selection';
      return;
    }

    try {
      const { res, data } = await apiPost('/api/llm/select', { model_key: selectedKey });
      if (res.ok) {
        updateLlmStatusDisplay(data);
      } else {
        console.error('Failed to select LLM model:', data.error);
        checkLlmStatus();
      }
    } catch (err) {
      console.error('Error selecting LLM model:', err);
      checkLlmStatus();
    }
  });
}

async function checkLlmStatus() {
  try {
    const status = await apiGet('/api/llm/status');
    updateLlmStatusDisplay(status);
  } catch (e) {
    const pill = document.getElementById('llm-status-pill');
    const text = document.getElementById('llm-status-text');
    const dot = pill ? pill.querySelector('.status-dot') : null;
    if (dot) {
      dot.classList.remove('status-active');
      dot.classList.add('status-inactive');
    }
    if (text) text.textContent = 'LLM: Unavailable';
    if (pill) pill.title = 'Could not reach LLM status API';
  }
}

// ============================================================
// THEME CONTROLLER (Dracula Dark / Clean Light)
// ============================================================

function initThemeController() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  const themeIcon = document.getElementById('theme-icon');
  const themeText = document.getElementById('theme-text');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('asclepius-theme', theme);
    if (themeIcon && themeText) {
      if (theme === 'light') {
        themeIcon.textContent = '☀️';
        themeText.textContent = 'Light';
      } else {
        themeIcon.textContent = '🌙';
        themeText.textContent = 'Dracula';
      }
    }
  }

  const currentTheme = localStorage.getItem('asclepius-theme') || 'dark';
  applyTheme(currentTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const activeTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      applyTheme(activeTheme);
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initThemeController);
} else {
  initThemeController();
}
