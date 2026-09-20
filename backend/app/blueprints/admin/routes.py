"""Admin console: full control over the doctor directory.

Every route is behind `admin_required`, which resolves the role from the
database on each request rather than trusting a value copied into the session
at login time.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from ...extensions import db
from ...models.doctor import Doctor, DoctorAvailability, Specialty
from ...utils.security import admin_required
from .validators import ValidationError, validate_availability, validate_doctor

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _apply(doctor: Doctor, payload: dict) -> None:
    """Copy a validated payload onto a Doctor, resolving the specialty name."""
    specialty_name = payload.pop("specialty", None)
    if specialty_name:
        doctor.specialty = Specialty.get_or_create(specialty_name)
    for field, value in payload.items():
        setattr(doctor, field, value)


def _invalid(error: ValidationError):
    return jsonify({"error": "Please correct the highlighted fields", "fields": error.errors}), 400


@admin_bp.get("/stats")
@admin_required
def stats():
    counts = dict(
        db.session.query(Doctor.approval_status, func.count(Doctor.id))
        .group_by(Doctor.approval_status)
        .all()
    )
    return jsonify(
        {
            "total": sum(counts.values()),
            "approved": counts.get(Doctor.STATUS_APPROVED, 0),
            "pending": counts.get(Doctor.STATUS_PENDING, 0),
            "rejected": counts.get(Doctor.STATUS_REJECTED, 0),
            "specialties": Specialty.query.count(),
        }
    )


@admin_bp.get("/doctors")
@admin_required
def list_doctors():
    """Every doctor regardless of status - this is the console's working list."""
    query = Doctor.query.outerjoin(Specialty)

    status = (request.args.get("status") or "").strip().lower()
    if status:
        query = query.filter(Doctor.approval_status == status)

    search = (request.args.get("q") or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Doctor.name.ilike(pattern),
                Doctor.hospital.ilike(pattern),
                Doctor.location.ilike(pattern),
                Specialty.name.ilike(pattern),
            )
        )

    doctors = query.order_by(Doctor.created_at.desc()).all()
    return jsonify([doctor.to_dict(include_availability=True) for doctor in doctors])


@admin_bp.get("/doctors/<int:doctor_id>")
@admin_required
def get_doctor(doctor_id: int):
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify(doctor.to_dict(include_availability=True))


@admin_bp.post("/doctors")
@admin_required
def create_doctor():
    body = request.get_json(silent=True) or {}
    try:
        payload = validate_doctor(body)
        windows = validate_availability(body) if "availability" in body else []
    except ValidationError as error:
        return _invalid(error)

    payload.setdefault("approval_status", Doctor.STATUS_APPROVED)
    doctor = Doctor()
    _apply(doctor, payload)
    db.session.add(doctor)
    db.session.flush()

    for window in windows:
        db.session.add(DoctorAvailability(doctor_id=doctor.id, **window))

    db.session.commit()
    return jsonify(doctor.to_dict(include_availability=True)), 201


@admin_bp.put("/doctors/<int:doctor_id>")
@admin_required
def update_doctor(doctor_id: int):
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    body = request.get_json(silent=True) or {}
    try:
        payload = validate_doctor(body, partial=True)
        windows = validate_availability(body) if "availability" in body else None
    except ValidationError as error:
        return _invalid(error)

    _apply(doctor, payload)

    if windows is not None:
        DoctorAvailability.query.filter_by(doctor_id=doctor.id).delete()
        for window in windows:
            db.session.add(DoctorAvailability(doctor_id=doctor.id, **window))

    db.session.commit()
    return jsonify(doctor.to_dict(include_availability=True))


@admin_bp.post("/doctors/<int:doctor_id>/status")
@admin_required
def set_status(doctor_id: int):
    """Approve or reject in one call, with an optional note for the doctor."""
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    body = request.get_json(silent=True) or {}
    try:
        payload = validate_doctor(
            {
                "approval_status": body.get("approval_status"),
                "rejection_note": body.get("rejection_note"),
            },
            partial=True,
        )
    except ValidationError as error:
        return _invalid(error)

    if "approval_status" not in payload:
        return jsonify({"error": "approval_status is required"}), 400

    doctor.approval_status = payload["approval_status"]
    doctor.rejection_note = (
        payload.get("rejection_note") if doctor.approval_status == Doctor.STATUS_REJECTED else None
    )
    db.session.commit()
    return jsonify(doctor.to_dict())


@admin_bp.delete("/doctors/<int:doctor_id>")
@admin_required
def delete_doctor(doctor_id: int):
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404
    db.session.delete(doctor)
    db.session.commit()
    return jsonify({"message": "Doctor removed"})


@admin_bp.get("/specialties")
@admin_required
def list_specialties():
    """All specialties, including any with no approved doctors yet."""
    return jsonify(
        [specialty.to_dict() for specialty in Specialty.query.order_by(Specialty.name).all()]
    )
