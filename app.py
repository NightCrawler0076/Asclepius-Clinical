"""
Doctor Voice-to-Prescription System — Flask Application

Refactored from the original monolithic transcriber into a modular
application following the plan's Phase 1 structure.

Existing three-input transcription is preserved.
New routes added: consultations, prescriptions, patients, doctors.

Run:
    python app.py
Then open http://localhost:5000
"""

import os
from io import BytesIO

from flask import Flask, jsonify, request, render_template, send_file, abort

from config import (
    MODEL_SIZES, DEFAULT_MODEL, MIC_WAV_PATH, SYSTEM_WAV_PATH,
    HOST, PORT, DEBUG, SECRET_KEY, ENABLE_SYSTEM_AUDIO,
)
from database.models import init_db
from database import repository as db
from audio import microphone
from audio.file_input import save_upload

# System/loopback capture depends on `soundcard` (PulseAudio/PipeWire on Linux).
# It is optional so the app still starts on a headless Raspberry Pi.
system_audio = None
_system_audio_error = "System audio capture is disabled (EMB_ENABLE_SYSTEM_AUDIO=0)"
if ENABLE_SYSTEM_AUDIO:
    try:
        from audio import system_audio
    except Exception as _e:  # ImportError, or soundcard failing to reach the audio server
        _system_audio_error = f"System audio capture unavailable: {_e}"
        print(_system_audio_error)
from asr.transcription import transcribe_audio
from prescription.generator import generate_from_transcript
from prescription.pdf_generator import generate_prescription_pdf
from clinical.rules import validate_prescription

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ============================================================
# STARTUP — initialize database
# ============================================================

init_db()


# ============================================================
# PAGE ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template("consultation.html", model_sizes=MODEL_SIZES, default_model=DEFAULT_MODEL)


@app.route("/consultation")
def consultation_page():
    return render_template("consultation.html", model_sizes=MODEL_SIZES, default_model=DEFAULT_MODEL)


@app.route("/prescription/<consultation_id>")
def prescription_page(consultation_id):
    return render_template("prescription.html", consultation_id=consultation_id)


# ============================================================
# API — DEVICE LISTS (preserved from original)
# ============================================================

@app.route("/api/input-devices")
def api_input_devices():
    try:
        devices = microphone.list_input_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/output-devices")
def api_output_devices():
    if system_audio is None:
        return jsonify([])
    try:
        devices = system_audio.list_output_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API — MICROPHONE (preserved from original)
# ============================================================

@app.route("/api/mic/start", methods=["POST"])
def api_mic_start():
    data = request.get_json(force=True)
    device_id = data.get("device_id")

    try:
        microphone.start(device_id)
        return jsonify({"status": "recording"})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not start recording: {e}"}), 500


@app.route("/api/mic/stop", methods=["POST"])
def api_mic_stop():
    data = request.get_json(force=True)
    model_size = data.get("model_size") or DEFAULT_MODEL

    try:
        wav_path = microphone.stop()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = transcribe_audio(wav_path, model_size)
        return jsonify({"text": result["text"], "audio_url": "/api/mic/audio"})
    except Exception as e:
        return jsonify({"error": f"Whisper transcription failed: {e}"}), 500


@app.route("/api/mic/audio")
def api_mic_audio():
    if not os.path.exists(MIC_WAV_PATH):
        abort(404)
    return send_file(MIC_WAV_PATH, mimetype="audio/wav")

# ============================================================
# API — SYSTEM / DEVICE AUDIO (preserved from original)
# ============================================================

@app.route("/api/system/start", methods=["POST"])
def api_system_start():
    if system_audio is None:
        return jsonify({"error": _system_audio_error}), 400
    data = request.get_json(force=True)
    device_name = data.get("device_name")
    try:
        system_audio.start(device_name)
        return jsonify({"status": "capturing"})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/system/stop", methods=["POST"])
def api_system_stop():
    if system_audio is None:
        return jsonify({"error": _system_audio_error}), 400
    data = request.get_json(force=True)
    model_size = data.get("model_size") or DEFAULT_MODEL

    try:
        wav_path = system_audio.stop()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = transcribe_audio(wav_path, model_size)
        return jsonify({"text": result["text"], "audio_url": "/api/system/audio"})
    except Exception as e:
        return jsonify({"error": f"Whisper transcription failed: {e}"}), 500


@app.route("/api/system/audio")
def api_system_audio():
    if not os.path.exists(SYSTEM_WAV_PATH):
        abort(404)
    return send_file(SYSTEM_WAV_PATH, mimetype="audio/wav")


# ============================================================
# API — FILE UPLOAD (preserved from original)
# ============================================================

@app.route("/api/file/transcribe", methods=["POST"])
def api_file_transcribe():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded = request.files["file"]
    model_size = request.form.get("model_size") or DEFAULT_MODEL

    try:
        tmp_path, basename = save_upload(uploaded)
        result = transcribe_audio(tmp_path, model_size)
        return jsonify({"text": result["text"], "download_name": basename + ".txt"})
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500


# ============================================================
# API — DOCTORS
# ============================================================

@app.route("/api/doctors", methods=["GET"])
def api_list_doctors():
    return jsonify(db.list_doctors())


@app.route("/api/doctors", methods=["POST"])
def api_create_doctor():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    doctor = db.create_doctor(
        name=name,
        specialty=data.get("specialty", ""),
        clinic_name=data.get("clinic_name", ""),
        phone=data.get("phone", ""),
    )
    return jsonify(doctor), 201


@app.route("/api/doctors/<doctor_id>", methods=["GET"])
def api_get_doctor(doctor_id):
    doctor = db.get_doctor(doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify(doctor)


@app.route("/api/doctors/<doctor_id>", methods=["DELETE"])
def api_delete_doctor(doctor_id):
    deleted = db.delete_doctor(doctor_id)
    if not deleted:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify({"status": "deleted", "id": doctor_id})


# ============================================================
# API — PATIENTS
# ============================================================

@app.route("/api/patients", methods=["GET"])
def api_list_patients():
    return jsonify(db.list_patients())


@app.route("/api/patients", methods=["POST"])
def api_create_patient():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    patient = db.create_patient(
        name=name,
        age=data.get("age"),
        sex=data.get("sex", ""),
        phone=data.get("phone", ""),
    )
    return jsonify(patient), 201


@app.route("/api/patients/<patient_id>", methods=["GET"])
def api_get_patient(patient_id):
    patient = db.get_patient(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(patient)


@app.route("/api/patients/<patient_id>", methods=["DELETE"])
def api_delete_patient(patient_id):
    deleted = db.delete_patient(patient_id)
    if not deleted:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify({"status": "deleted", "id": patient_id})


# ============================================================
# API — CONSULTATIONS
# ============================================================

@app.route("/api/consultations", methods=["GET"])
def api_list_consultations():
    doctor_id = request.args.get("doctor_id")
    return jsonify(db.list_consultations(doctor_id))


@app.route("/api/consultations", methods=["POST"])
def api_create_consultation():
    data = request.get_json(force=True)
    doctor_id = data.get("doctor_id", "").strip()
    if not doctor_id:
        return jsonify({"error": "doctor_id is required"}), 400
    consultation = db.create_consultation(
        doctor_id=doctor_id,
        patient_id=data.get("patient_id"),
        audio_path=data.get("audio_path", ""),
    )
    return jsonify(consultation), 201


@app.route("/api/consultations/<consultation_id>")
def api_get_consultation(consultation_id):
    consultation = db.get_consultation(consultation_id)
    if not consultation:
        return jsonify({"error": "Consultation not found"}), 404
    return jsonify(consultation)


# ============================================================
# API — TRANSCRIPTS
# ============================================================

@app.route("/api/consultations/<consultation_id>/transcript", methods=["POST"])
def api_save_transcript(consultation_id):
    """Save a transcript for a consultation."""
    request_data = request.get_json(force=True)
    text = request_data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    transcript_id = db.save_transcript(
        consultation_id=consultation_id,
        text=text,
        language=request_data.get("language", ""),
        model_used=request_data.get("model_used", ""),
        segments=request_data.get("segments"),
    )
    return jsonify({"transcript_id": transcript_id}), 201


@app.route("/api/consultations/<consultation_id>/transcript")
def api_get_transcript(consultation_id):
    transcript = db.get_transcript(consultation_id)
    if not transcript:
        return jsonify({"error": "No transcript found"}), 404
    return jsonify(transcript)


# ============================================================
# API — PRESCRIPTIONS
# ============================================================

@app.route("/api/consultations/<consultation_id>/prescription/generate", methods=["POST"])
def api_generate_prescription(consultation_id):
    """Generate a draft prescription from the consultation's transcript."""
    transcript = db.get_transcript(consultation_id)
    if not transcript:
        return jsonify({"error": "No transcript found for this consultation"}), 404

    request_data = request.get_json(silent=True) or {}
    llm_model_key = request_data.get("llm_model")

    # Get patient info if available
    consultation = db.get_consultation(consultation_id)
    patient = None
    if consultation and consultation.get("patient_id"):
        patient = db.get_patient(consultation["patient_id"])

    patient_dict = None
    if patient:
        patient_dict = {
            "name": patient.get("name", ""),
            "age": patient.get("age"),
            "sex": patient.get("sex", ""),
            "patient_id": patient.get("id", ""),
        }

    prescription = generate_from_transcript(
        transcript_text=transcript["text"],
        doctor_id=consultation.get("doctor_id", "") if consultation else "",
        patient=patient_dict,
        llm_model_key=llm_model_key,
    )

    # Validate
    warnings = validate_prescription(prescription)

    # Save to database
    prescription_id = db.save_prescription(consultation_id, prescription, "draft")

    return jsonify({
        "prescription_id": prescription_id,
        "prescription": prescription,
        "warnings": warnings,
    }), 201


@app.route("/api/consultations/<consultation_id>/prescription")
def api_get_prescription(consultation_id):
    prescription_record = db.get_prescription(consultation_id)
    if not prescription_record:
        return jsonify({"error": "No prescription found"}), 404
    return jsonify(prescription_record)


@app.route("/api/prescriptions/<int:prescription_id>", methods=["PUT"])
def api_update_prescription(prescription_id):
    """Update prescription data and/or status."""
    request_data = request.get_json(force=True)
    prescription_data = request_data.get("data")
    status = request_data.get("status", "draft")

    if prescription_data is None:
        return jsonify({"error": "data is required"}), 400

    try:
        db.update_prescription(prescription_id, prescription_data, status)
        return jsonify({"status": "updated"})
    except Exception as update_error:
        return jsonify({"error": str(update_error)}), 500


@app.route("/api/prescriptions/<int:prescription_id>/confirm", methods=["POST"])
def api_confirm_prescription(prescription_id):
    """Confirm a draft prescription — doctor sign-off."""
    prescription_record = db.get_prescription_by_id(prescription_id)
    if not prescription_record:
        return jsonify({"error": "Prescription not found"}), 404

    prescription_data = prescription_record["data"]
    prescription_data["status"] = "confirmed"

    db.update_prescription(prescription_id, prescription_data, "confirmed")

    return jsonify({"status": "confirmed", "prescription_id": prescription_id})


@app.route("/api/prescriptions", methods=["GET"])
def api_list_all_prescriptions():
    """List all saved prescriptions across all consultations."""
    return jsonify(db.list_all_prescriptions())


@app.route("/api/prescriptions/<int:prescription_id>", methods=["DELETE"])
def api_delete_prescription(prescription_id):
    """Delete a prescription record."""
    is_deleted = db.delete_prescription(prescription_id)
    if not is_deleted:
        return jsonify({"error": "Prescription not found"}), 404
    return jsonify({"status": "deleted", "prescription_id": prescription_id})


@app.route("/api/prescriptions/<int:prescription_id>/pdf", methods=["GET"])
def api_download_prescription_pdf(prescription_id):
    """Generate and download a PDF document for a prescription ID."""
    prescription_record = db.get_prescription_by_id(prescription_id)
    if not prescription_record:
        return jsonify({"error": "Prescription not found"}), 404

    prescription_data = prescription_record.get("data") or {}
    prescription_data["prescription_id"] = prescription_id
    
    # Fetch doctor info if consultation exists
    doctor_info = None
    consultation_id = prescription_record.get("consultation_id")
    if consultation_id:
        consultation_record = db.get_consultation(consultation_id)
        if consultation_record and consultation_record.get("doctor_id"):
            doctor_info = db.get_doctor(consultation_record["doctor_id"])

    pdf_bytes = generate_prescription_pdf(
        rx_data=prescription_data,
        doctor_info=doctor_info,
        status=prescription_record.get("status", "draft"),
    )

    pdf_filename = f"prescription_{prescription_id}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_filename,
    )


@app.route("/api/consultations/<consultation_id>/prescription/pdf", methods=["GET"])
def api_download_consultation_prescription_pdf(consultation_id):
    """Generate and download a PDF document for a consultation's latest prescription."""
    prescription_record = db.get_prescription(consultation_id)
    if not prescription_record:
        return jsonify({"error": "Prescription not found for this consultation"}), 404

    prescription_data = prescription_record.get("data") or {}
    prescription_data["prescription_id"] = prescription_record.get("id")
    
    doctor_info = None
    consultation_record = db.get_consultation(consultation_id)
    if consultation_record and consultation_record.get("doctor_id"):
        doctor_info = db.get_doctor(consultation_record["doctor_id"])

    pdf_bytes = generate_prescription_pdf(
        rx_data=prescription_data,
        doctor_info=doctor_info,
        status=prescription_record.get("status", "draft"),
    )

    pdf_filename = f"prescription_{consultation_id}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_filename,
    )


# ============================================================
# API — LLM STATUS & SELECTION
# ============================================================

@app.route("/api/llm/status")
def api_llm_status():
    """Return the current LLM refinement status for the UI."""
    from clinical.llm_refiner import get_status
    return jsonify(get_status())


@app.route("/api/llm/models", methods=["GET"])
def api_llm_models():
    """List all registered LLM models and their download/active status."""
    from clinical.llm_refiner import list_available_models
    return jsonify(list_available_models())


@app.route("/api/llm/select", methods=["POST"])
def api_llm_select():
    """Select the active LLM model."""
    from clinical.llm_refiner import set_active_model
    data = request.get_json(force=True)
    model_key = data.get("model_key", "").strip()
    if not model_key:
        return jsonify({"error": "model_key is required"}), 400
    try:
        status = set_active_model(model_key)
        return jsonify(status)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to switch model: {e}"}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)