"""Prescription persistence. OCR is client-side; only patient-verified data is stored."""
from flask import Blueprint, jsonify, request
from ...extensions import db
from ...models.notification import Notification
from ...models.prescription import Prescription
from ...models.reminder import MedicationReminder
from ...utils.security import patient_required, current_user

prescriptions_bp = Blueprint("prescriptions", __name__, url_prefix="/api/prescriptions")


@prescriptions_bp.get("")
@patient_required
def list_prescriptions():
    rows = Prescription.query.filter_by(patient_id=current_user().id).order_by(Prescription.created_at.desc()).all()
    return jsonify({"prescriptions": [row.to_dict() for row in rows]})


@prescriptions_bp.post("")
@patient_required
def create_prescription():
    data = request.get_json(silent=True) or {}
    raw_text = str(data.get("raw_text") or "").strip()
    items = data.get("items")
    if not raw_text or len(raw_text) > 30000:
        return jsonify({"error": "Prescription text is required (maximum 30,000 characters)"}), 400
    if not isinstance(items, list) or len(items) > 100:
        return jsonify({"error": "Verified medicine items must be a list"}), 400
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            return jsonify({"error": "Each medicine entry must be an object"}), 400
        name = str(item.get("medicine_name") or "").strip()
        dosage = str(item.get("dosage") or "").strip()
        frequency = str(item.get("frequency") or "").strip()
        if not name or len(name) > 160:
            return jsonify({"error": "Each medicine needs a valid name"}), 400
        if not dosage or not frequency:
            return jsonify({"error": "Verify the dosage and frequency for every medicine"}), 400
        cleaned.append({
            "medicine_name": name,
            "dosage": dosage[:120],
            "frequency": frequency[:120],
            "duration": str(item.get("duration") or "").strip()[:500],
            "instructions": str(item.get("instructions") or "").strip()[:500],
        })
    if not cleaned:
        return jsonify({"error": "Add and verify at least one medicine before saving"}), 400
    row = Prescription(patient_id=current_user().id, raw_text=raw_text, items=cleaned, verified=True)
    db.session.add(row)
    db.session.flush()
    db.session.add(Notification(patient_id=current_user().id, kind="new_prescription",
        title="Prescription saved", message="Your verified prescription was saved successfully.",
        dedupe_key=f"prescription-saved:{row.id}"))
    db.session.commit()
    return jsonify({"prescription": row.to_dict()}), 201


@prescriptions_bp.delete("/<int:prescription_id>")
@patient_required
def delete_prescription(prescription_id):
    row = Prescription.query.filter_by(id=prescription_id, patient_id=current_user().id).first()
    if row is None:
        return jsonify({"error": "Prescription not found"}), 404
    # Keep medication plans and their dose history intact if this source record is removed.
    MedicationReminder.query.filter_by(prescription_id=row.id).update(
        {"prescription_id": None}, synchronize_session=False)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Prescription deleted"})
