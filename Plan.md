# Product Development Plan — Doctor Voice-to-Prescription System

## 1. Product Goal

Build a desktop/laptop-based clinical assistant that captures a doctor's speech through multiple audio-input methods, isolates the doctor's voice, converts it into text, extracts clinically relevant information, generates a structured prescription draft, allows the doctor to review and edit it, stores the consultation locally, and synchronizes records to a server when connectivity is available.

The system is an **assistive prescription-drafting tool**, not an autonomous medical decision-maker. The doctor remains responsible for reviewing and confirming every prescription.

The current `Emb` prototype already establishes the transcription foundation: Flask UI, microphone capture, system-audio loopback, file upload, Whisper model selection, audio playback, and text export.

## 2. Existing Foundation

### Already implemented

- Flask web application
- Three transcription modes:
  - Microphone
  - System/device audio
  - Audio/video file upload
- Input/output device enumeration
- WAV recording
- OpenAI Whisper transcription
- Whisper model caching
- Basic transcription result display
- TXT download
- Basic browser UI
- Windows system-audio COM handling
- ffmpeg-based audio/video decoding

### Existing API structure

```text
GET  /api/input-devices
GET  /api/output-devices

POST /api/mic/start
POST /api/mic/stop
GET  /api/mic/audio

POST /api/system/start
POST /api/system/stop
GET  /api/system/audio

POST /api/file/transcribe
```

This should become the **Audio/ASR subsystem**, rather than being thrown away.

---

# 3. Target Product Architecture

```text
                 ┌─────────────────────────┐
                 │       Doctor UI         │
                 │ Flask + HTML/JS         │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Consultation Controller│
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Audio Manager      │
                 │ mic / loopback / file   │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Audio Preprocessing     │
                 │ resampling / VAD /      │
                 │ denoising / segmentation│
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Speaker Processing      │
                 │ diarization + doctor    │
                 │ voice matching          │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Speech Recognition      │
                 │ faster-whisper /        │
                 │ Whisper                 │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Clinical NLP            │
                 │ NER + dictionary +      │
                 │ rules + normalization   │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Prescription Engine     │
                 │ structured JSON         │
                 └────────────┬────────────┘
                              │
                       ┌──────┴──────┐
                       ▼             ▼
              ┌─────────────┐ ┌──────────────┐
              │ Doctor      │ │ PDF/Print    │
              │ Review      │ │ Generation   │
              └──────┬──────┘ └──────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Local DB     │
              │ SQLite       │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Sync Queue   │
              │ SQLite       │
              └──────┬───────┘
                     │
              Internet available
                     │
                     ▼
              ┌──────────────┐
              │ Backend API  │
              │ PostgreSQL   │
              └──────────────┘
```

---

# 4. Development Phases

## Phase 1 — Refactor the Existing Transcriber

Turn the current single-file Flask prototype into a modular application.

Suggested structure:

```text
doctor-assistant/
├── app.py
├── config.py
├── requirements.txt
│
├── audio/
│   ├── microphone.py
│   ├── system_audio.py
│   ├── file_input.py
│   ├── preprocessing.py
│   └── vad.py
│
├── asr/
│   ├── whisper_engine.py
│   └── transcription.py
│
├── speaker/
│   ├── enrollment.py
│   ├── diarization.py
│   └── matcher.py
│
├── clinical/
│   ├── extractor.py
│   ├── normalizer.py
│   ├── medicines.py
│   └── rules.py
│
├── prescription/
│   ├── schema.py
│   ├── generator.py
│   └── pdf.py
│
├── database/
│   ├── models.py
│   ├── repository.py
│   └── migrations.py
│
├── sync/
│   ├── outbox.py
│   └── client.py
│
├── templates/
├── static/
└── tests/
```

Do not change the working three-input capability.

---

# 5. Phase 2 — Better ASR Pipeline

Replace the basic:

```text
record → Whisper → text
```

with:

```text
record
   ↓
normalize audio
   ↓
VAD
   ↓
speech segments
   ↓
speaker processing
   ↓
ASR
   ↓
timestamped transcript
```

For standard hardware, use **faster-whisper** as the primary ASR implementation.

Support configurable models:

```text
tiny
base
small
medium
large-v3
```

The model should be loaded once and reused.

Store:

- transcript
- language
- segment start/end
- confidence where available
- source audio reference
- model used

---

# 6. Phase 3 — Doctor Voice Enrollment

Add a one-time doctor enrollment workflow.

```text
Doctor Registration
        ↓
Record voice sample
        ↓
Validate recording
        ↓
Generate speaker embedding
        ↓
Store encrypted/local voiceprint
        ↓
Doctor profile created
```

The PDF specifically proposes recording a short sample, computing a speaker embedding, and storing it as the doctor's voiceprint.

For standard hardware, use a stronger speaker-embedding solution than the lightweight edge configuration.

Potential pipeline:

```text
Audio
 ↓
VAD
 ↓
Speaker embedding model
 ↓
Embedding vector
 ↓
Cosine similarity
```

Never rely on speaker matching alone for prescription safety.

---

# 7. Phase 4 — Speaker Diarization

During consultation:

```text
Doctor ────────────────┐
                       │
Patient ───────────────┤ Audio
                       │
Attendant ─────────────┘
             ↓
       Diarization
             ↓
 Speaker 1 / Speaker 2 / Speaker 3
             ↓
 Compare embeddings
             ↓
 Doctor segments
```

The PDF explicitly specifies diarization followed by target-speaker matching so only matching doctor segments are retained.

Use a configurable diarization module so the implementation can be changed without modifying the rest of the system.

---

# 8. Phase 5 — Clinical NLP

Convert:

```text
"I have had fever for three days.
Give paracetamol 500 mg three times a day for five days."
```

into structured information:

```json
{
  "symptoms": [
    {
      "name": "fever",
      "duration": "3 days"
    }
  ],
  "medications": [
    {
      "name": "paracetamol",
      "dose": "500 mg",
      "frequency": "three times a day",
      "duration": "5 days"
    }
  ]
}
```

Extract at minimum:

- Patient complaints
- Symptoms
- Duration
- Diagnosis
- Medicines
- Dosage
- Route
- Frequency
- Duration
- Investigations
- Follow-up instructions
- Doctor notes

Use a hybrid approach:

```text
Transformer NER
       +
Medical dictionary
       +
Regex
       +
Normalization
       +
Rule engine
```

The PDF specifically identifies symptoms, diagnosis, medicines, dosage, frequency and duration as required clinical entities.

---

# 9. Phase 6 — Medical Entity Normalization

Do not directly put raw ASR output into the prescription.

Example:

```text
"para 500"
"paracetamol five hundred"
"PCM 500"
```

should potentially normalize toward:

```text
Paracetamol — 500 mg
```

Create a normalization layer:

```text
ASR text
 ↓
Entity detection
 ↓
Candidate normalization
 ↓
Confidence score
 ↓
Doctor confirmation
```

If confidence is low:

```text
⚠ Needs Review
```

rather than silently guessing.

---

# 10. Phase 7 — Prescription Schema

Define one canonical prescription object.

Example:

```json
{
  "consultation_id": "CONS-001",
  "doctor_id": "DOC-001",
  "patient": {
    "name": "",
    "age": null,
    "sex": "",
    "patient_id": ""
  },
  "complaints": [],
  "diagnosis": [],
  "medications": [
    {
      "name": "",
      "dose": "",
      "route": "",
      "frequency": "",
      "duration": "",
      "instructions": ""
    }
  ],
  "investigations": [],
  "advice": [],
  "follow_up": "",
  "doctor_notes": "",
  "created_at": "",
  "status": "draft"
}
```

The prescription engine must generate this object before generating a PDF.

---

# 11. Phase 8 — Doctor Review Interface

This is one of the most important product phases.

The doctor should see:

```text
┌─────────────────────────────────────┐
│ Patient Information                 │
├─────────────────────────────────────┤
│ Symptoms                             │
│ [ Fever ] [ 3 days ]                 │
├─────────────────────────────────────┤
│ Diagnosis                            │
│ [ __________________________ ]      │
├─────────────────────────────────────┤
│ Medicines                            │
│ Paracetamol | 500mg | 3x/day | 5d  │
│ [Edit] [Delete]                      │
├─────────────────────────────────────┤
│ Advice                               │
│ [ __________________________ ]      │
├─────────────────────────────────────┤
│ [Save Draft] [Generate PDF]         │
│ [Confirm Prescription]               │
└─────────────────────────────────────┘
```

The doctor must explicitly confirm before the prescription becomes final.

The PDF describes this review/edit/confirm step as part of the intended operational flow.

---

# 12. Phase 9 — Patient and Consultation Management

Create database entities:

```text
Doctor
Patient
Consultation
Transcript
ClinicalEntity
Prescription
Medication
SyncJob
AuditEvent
```

Relationships:

```text
Doctor
  │
  └── Consultations
          │
          ├── Patient
          ├── Audio
          ├── Transcript
          ├── Clinical Entities
          └── Prescription
```

Use SQLite locally.

---

# 13. Phase 10 — Local-First Storage

Every consultation should be usable without internet.

Store:

```text
data/
├── doctors/
├── patients/
├── consultations/
│   └── CONS-001/
│       ├── audio.wav
│       ├── transcript.json
│       ├── prescription.json
│       └── prescription.pdf
└── database.sqlite
```

The PDF calls for authoritative local consultation folders and an SQLite outbox queue.

---

# 14. Phase 11 — Offline Sync

Implement:

```text
Local Save
    ↓
SQLite outbox
    ↓
Internet check
    ↓
Upload pending records
    ↓
Server acknowledgement
    ↓
Mark synced
```

Important properties:

- Retry failed uploads
- Exponential backoff
- Idempotency keys
- Never delete local records before server acknowledgement
- Handle duplicate uploads
- Maintain sync status

The intended architecture already specifies opportunistic background synchronization when connectivity becomes available.

---

# 15. Phase 12 — Backend

For the standard-computation version:

```text
Flask frontend/API
        ↓
REST backend
        ↓
PostgreSQL
```

Possible production architecture:

```text
Desktop Client
      │
      │ HTTPS
      ▼
Backend API
      │
 ┌────┴─────┐
 ▼          ▼
PostgreSQL Object Storage
```

The PDF identifies PostgreSQL or Firebase as possible cloud integrations using HTTPS REST and TLS 1.2+.

Start with PostgreSQL because the product has relational entities and audit requirements.

---

# 16. Phase 13 — PDF Prescription

Generate a professional printable prescription.

Include:

- Doctor information
- Clinic information
- Patient information
- Date/time
- Symptoms
- Diagnosis
- Medication table
- Investigations
- Advice
- Follow-up
- Prescription ID
- Doctor confirmation status

Use ReportLab as specified in the source architecture.

---

# 17. Phase 14 — Security

Before calling the system production-ready, add:

- User authentication
- Doctor accounts
- Role-based access
- Local encryption for sensitive data
- HTTPS
- Database access control
- Audit logging
- Secure session handling
- File upload validation
- Path traversal protection
- Secrets in environment variables
- No sensitive information in application logs
- Automatic session timeout
- Backup/restore mechanism

Medical data must never be treated like ordinary application data.

---

# 18. Phase 15 — Testing

Create tests for:

### Audio

- Microphone capture
- System loopback
- File upload
- Invalid files
- Empty recordings

### ASR

- Clean speech
- Noisy speech
- Indian accents
- Medical terminology
- Mixed English/Indian-language speech

### Speaker

- Correct doctor
- Wrong speaker
- Multiple speakers
- Similar voices
- Poor-quality recording

### NLP

- Medicine extraction
- Dosage extraction
- Frequency extraction
- Duration extraction
- Missing entities
- Ambiguous entities

### Prescription

- Correct JSON
- PDF generation
- Editing
- Confirmation
- Persistence

### Offline

- No internet
- Internet restored
- Failed upload
- Duplicate upload
- Partial sync

---

# 19. Product Milestones

## M1 — Existing Transcriber Stabilized

Three input methods work reliably.

## M2 — Consultation Pipeline

```text
Audio → VAD → ASR → Transcript
```

## M3 — Doctor Identity

```text
Enrollment → Speaker Embedding → Matching
```

## M4 — Clinical Intelligence

```text
Transcript → Clinical Entities
```

## M5 — Prescription

```text
Entities → Prescription JSON → Doctor Review → PDF
```

## M6 — Local EHR

```text
Patient → Consultation → Prescription → History
```

## M7 — Cloud Sync

```text
SQLite Outbox → Backend → PostgreSQL
```

## M8 — Production Hardening

Security, audit, testing, backup, error handling and deployment.

---

# 20. Recommended Build Order

Do **not** build everything simultaneously.

Build in this exact order:

```text
1. Refactor existing Flask app
       ↓
2. Stable three-input audio layer
       ↓
3. VAD
       ↓
4. Better Whisper/faster-whisper pipeline
       ↓
5. Doctor enrollment
       ↓
6. Speaker diarization
       ↓
7. Target-speaker filtering
       ↓
8. Clinical NER
       ↓
9. Entity normalization
       ↓
10. Prescription JSON
       ↓
11. Doctor review UI
       ↓
12. PDF generation
       ↓
13. SQLite patient/consultation database
       ↓
14. Offline outbox
       ↓
15. Backend + PostgreSQL
       ↓
16. Sync
       ↓
17. Security
       ↓
18. Testing
       ↓
19. Packaging/deployment
```

This order minimizes rework and gets a usable end-to-end prototype early.

---

# 21. Definition of Done

The product is ready for a serious prototype demonstration when a doctor can:

1. Register their voice.
2. Create/select a patient.
3. Start a consultation.
4. Speak naturally.
5. Stop the consultation.
6. Have the system isolate the doctor's speech.
7. Generate a transcript.
8. Extract clinical information.
9. Produce a structured prescription.
10. Review and edit it.
11. Confirm it.
12. Generate a PDF.
13. Reopen the consultation later.
14. Use the system without internet.
15. Automatically synchronize pending records when internet returns.

The system should never automatically finalize a prescription without doctor review.