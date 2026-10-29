"""
Comprehensive integration test for Flask routes and prescription flow.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database.models import init_db

init_db()
client = app.test_client()

def test_home_page():
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Asclepius Clinical" in html
    assert "Whisper Small" in html
    assert "Whisper Base" in html
    assert "Whisper Medium" in html
    assert "Whisper Large" not in html
    print("[PASS] Home page renders cleanly without Whisper Large")

def test_device_apis():
    res = client.get("/api/input-devices")
    assert res.status_code == 200
    devices = json.loads(res.data)
    assert isinstance(devices, list)

    res = client.get("/api/output-devices")
    assert res.status_code == 200
    out_devices = json.loads(res.data)
    assert isinstance(out_devices, list)
    print("[PASS] Device listing APIs operational")

def test_full_clinical_workflow():
    doc_id = None
    pat_id = None
    cons_id = None
    try:
        # 1. Create doctor
        doc_res = client.post("/api/doctors", json={"name": "Dr. Test Physician", "specialty": "Internal Medicine"})
        assert doc_res.status_code == 201
        doc = json.loads(doc_res.data)
        doc_id = doc["id"]

        # 2. Create patient
        pat_res = client.post("/api/patients", json={"name": "Patient Test", "age": 42, "sex": "Male"})
        assert pat_res.status_code == 201
        pat = json.loads(pat_res.data)
        pat_id = pat["id"]

        # 3. Create consultation
        cons_res = client.post("/api/consultations", json={"doctor_id": doc_id, "patient_id": pat_id})
        assert cons_res.status_code == 201
        cons = json.loads(cons_res.data)
        cons_id = cons["id"]

        # 4. Save transcript
        transcript_text = "Patient has high grade fever for 3 days and dry cough. Acute Bronchitis. Prescribe Augmentin 625mg twice daily for 5 days and Dolo 650mg thrice daily for 3 days. Do a CBC test. Review in 1 week."
        tx_res = client.post(f"/api/consultations/{cons_id}/transcript", json={"text": transcript_text})
        assert tx_res.status_code == 201

        # 5. Generate prescription
        gen_res = client.post(f"/api/consultations/{cons_id}/prescription/generate", json={})
        assert gen_res.status_code == 201
        rx_json = json.loads(gen_res.data)
        assert "prescription" in rx_json
        rx = rx_json["prescription"]
        assert len(rx["medications"]) >= 2
        med_names = [m["name"].lower() for m in rx["medications"]]
        assert any("augmentin" in m or "amoxicillin" in m for m in med_names)
        assert any("dolo" in m or "paracetamol" in m for m in med_names)

        # 6. Get prescription via API (verifying repository record)
        get_rx_res = client.get(f"/api/consultations/{cons_id}/prescription")
        assert get_rx_res.status_code == 200
        stored_rx = json.loads(get_rx_res.data)
        assert "data" in stored_rx

        # 7. View prescription HTML page
        rx_page = client.get(f"/prescription/{cons_id}")
        assert rx_page.status_code == 200
        rx_html = rx_page.data.decode("utf-8")
        assert "Prescription Detail" in rx_html
        assert "download-pdf-link" in rx_html

        # 8. Download PDF
        pdf_res = client.get(f"/api/consultations/{cons_id}/prescription/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.mimetype == "application/pdf"
        assert pdf_res.data.startswith(b"%PDF-")
        print(f"[PASS] PDF generated successfully ({len(pdf_res.data)} bytes)")
    finally:
        # Clean up test records
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        if cons_id:
            conn.execute("DELETE FROM prescriptions WHERE consultation_id = ?", (cons_id,))
            conn.execute("DELETE FROM transcripts WHERE consultation_id = ?", (cons_id,))
            conn.execute("DELETE FROM consultations WHERE id = ?", (cons_id,))
        if pat_id:
            conn.execute("DELETE FROM patients WHERE id = ?", (pat_id,))
        if doc_id:
            conn.execute("DELETE FROM doctors WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()

    print("[PASS] Full clinical consultation and prescription workflow verified 100%!")

if __name__ == "__main__":
    test_home_page()
    test_device_apis()
    test_full_clinical_workflow()
    print("\nALL INTEGRATION TESTS PASSED CLEANLY!")
