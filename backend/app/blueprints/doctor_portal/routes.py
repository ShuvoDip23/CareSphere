"""The doctor's own view of the system.

In the prototype a doctor could log in and then saw exactly what a patient
saw: nothing addressed to them. These endpoints are the other half of the
booking module - who booked you, why, and when you are open.

Every route resolves the Doctor row from the signed-in account rather than
from a path parameter. There is deliberately no `/api/doctor/<id>/...` route
anywhere in this file: if the id never travels in the URL, no handler can
forget to check that it belongs to the caller.
"""

from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request

from ...extensions import db
from ...models.appointment import Appointment
from ...models.doctor import Doctor, DoctorAvailability, Specialty
from ...utils.security import current_user, doctor_required
from ..admin.validators import ValidationError, validate_availability, validate_doctor

doctor_bp = Blueprint("doctor_portal", __name__, url_prefix="/api/doctor")

UPCOMING_LIMIT = 200
PAST_LIMIT = 100


def _profile() -> Doctor | None:
    """The Doctor row belonging to the signed-in account."""
    user = current_user()
    return Doctor.query.filter_by(user_id=user.id).first() if user else None


def _unlinked():
    """A doctor account with no profile attached to it.

    Possible today because the link is made by a CLI command. Once doctors
    register themselves the two are created together and this becomes
    unreachable - but it stays, because an account in a half-made state
    should get a clear answer rather than a 500.
    """
    return jsonify(
        {
            "error": "This account is not linked to a doctor profile yet. "
            "Ask an administrator to finish setting it up."
        }
    ), 409


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _serialise(appointment: Appointment) -> dict:
    """What the doctor is shown about one booking.

    Deliberately not `Appointment.to_dict()`: that payload is built for the
    patient and repeats the doctor's own hospital and phone number back at
    them. This one carries the patient instead.
    """
    return {
        "id": appointment.id,
        "scheduled_for": appointment.scheduled_for.isoformat(),
        "date": appointment.scheduled_for.strftime("%Y-%m-%d"),
        "time": appointment.scheduled_for.strftime("%H:%M"),
        "reason": appointment.reason,
        "status": appointment.status,
        "payment_status": appointment.payment_status,
        "fee": float(appointment.fee_at_booking),
        "is_past": appointment.is_past,
        "can_set_outcome": appointment.is_past
        and appointment.status != Appointment.STATUS_CANCELLED,
        "patient": {
            "name": appointment.patient.name if appointment.patient else "Unknown",
            "email": appointment.patient.email if appointment.patient else None,
        },
    }


# ------------------------------------------------------------------- routes


@doctor_bp.get("/me")
@doctor_required
def my_profile():
    """Profile and approval state for the signed-in doctor.

    A pending or rejected doctor still reaches this endpoint - being able to
    read your own rejection note is the point of having one.
    """
    doctor = _profile()
    if doctor is None:
        return _unlinked()
    return jsonify(doctor.to_dict(include_availability=True))


@doctor_bp.get("/appointments")
@doctor_required
def my_appointments():
    """Bookings for the signed-in doctor.

    `scope` is one of today | upcoming | past | all (default today).
    """
    doctor = _profile()
    if doctor is None:
        return _unlinked()

    scope = (request.args.get("scope") or "today").strip().lower()
    now = _now()
    query = Appointment.query.filter(Appointment.doctor_id == doctor.id)

    if scope == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(
            Appointment.scheduled_for >= start,
            Appointment.scheduled_for < start + timedelta(days=1),
        ).order_by(Appointment.scheduled_for.asc())
    elif scope == "upcoming":
        query = query.filter(Appointment.scheduled_for >= now).order_by(
            Appointment.scheduled_for.asc()
        )
    elif scope == "past":
        query = query.filter(Appointment.scheduled_for < now).order_by(
            Appointment.scheduled_for.desc()
        )
    else:
        scope = "all"
        query = query.order_by(Appointment.scheduled_for.desc())

    limit = PAST_LIMIT if scope in ("past", "all") else UPCOMING_LIMIT
    rows = query.limit(limit).all()
    return jsonify({"scope": scope, "items": [_serialise(row) for row in rows]})


@doctor_bp.post("/appointments/<int:appointment_id>/outcome")
@doctor_required
def set_outcome(appointment_id: int):
    """Close out a past appointment as completed or no-show."""
    doctor = _profile()
    if doctor is None:
        return _unlinked()

    appointment = db.session.get(Appointment, appointment_id)
    # Another doctor's appointment reads as missing, not forbidden, so the
    # endpoint cannot be used to count anyone else's bookings.
    if appointment is None or appointment.doctor_id != doctor.id:
        return jsonify({"error": "Appointment not found"}), 404

    outcome = str((request.get_json(silent=True) or {}).get("status") or "").strip().lower()
    if outcome not in Appointment.DOCTOR_OUTCOMES:
        return jsonify({"error": "Status must be completed or no_show"}), 400

    if appointment.status == Appointment.STATUS_CANCELLED:
        return jsonify({"error": "A cancelled appointment has no outcome to record"}), 400
    if not appointment.is_past:
        # Marking a future visit complete would let a doctor close out a
        # consultation that has not happened yet.
        return jsonify({"error": "This appointment has not happened yet"}), 400

    # Re-marking is allowed on purpose: recording the wrong outcome is an easy
    # mistake, and there is no reason to make a doctor ask an admin to fix it.
    appointment.status = outcome
    db.session.commit()
    return jsonify(_serialise(appointment))


@doctor_bp.get("/availability")
@doctor_required
def my_availability():
    doctor = _profile()
    if doctor is None:
        return _unlinked()
    return jsonify([window.to_dict() for window in doctor.availability])


@doctor_bp.put("/availability")
@doctor_required
def replace_availability():
    """Replace the whole weekly schedule with the submitted one.

    Replace rather than patch, because the editor sends the full week and a
    removed window has to actually disappear. Validation is the admin
    console's - one set of rules means the two editors cannot drift apart.
    """
    doctor = _profile()
    if doctor is None:
        return _unlinked()

    try:
        windows = validate_availability(request.get_json(silent=True) or {})
    except ValidationError as error:
        return jsonify(
            {"error": "Please correct the highlighted fields", "fields": error.errors}
        ), 400

    DoctorAvailability.query.filter_by(doctor_id=doctor.id).delete()
    for window in windows:
        db.session.add(DoctorAvailability(doctor_id=doctor.id, **window))
    db.session.commit()

    # Already-booked appointments are left alone. Removing a window stops new
    # bookings; it does not cancel patients who booked while it was open, and
    # silently deleting their appointments here would be far worse than
    # leaving the doctor to cancel them deliberately.
    return jsonify([window.to_dict() for window in doctor.availability])


def _changed_reviewed_fields(doctor: Doctor, payload: dict) -> list[str]:
    """Which identity fields this edit would actually change.

    Compares values rather than trusting that a key was sent: an editor that
    posts the whole form would otherwise re-open a review every time a doctor
    touched their bio.
    """
    changed = []
    for field in Doctor.REVIEWED_FIELDS:
        if field not in payload:
            continue
        if field == "specialty":
            current = doctor.specialty.name if doctor.specialty else None
        else:
            current = getattr(doctor, field)
        new = payload[field]
        if str(current or "").strip() != str(new or "").strip():
            changed.append(field)
    return changed


FIELD_LABELS = {
    "name": "name",
    "specialty": "specialty",
    "qualification": "qualification",
    "hospital": "hospital",
    "location": "location",
}


@doctor_bp.put("/profile")
@doctor_required
def update_profile():
    """Edit your own profile.

    Not every edit is equal. Consulting hours, bio, phone and fee describe how
    a doctor operates and apply at once - making someone wait for an admin to
    publish a corrected phone number helps nobody.

    Name, specialty, qualification, hospital and location are the claims the
    administrator approved. Changing one re-opens the question they answered,
    so the profile goes back in the queue and leaves the directory until it is
    looked at again. Appointments already booked are untouched; only new
    bookings stop, exactly as when a consulting window is removed.
    """
    doctor = _profile()
    if doctor is None:
        return _unlinked()

    body = request.get_json(silent=True) or {}
    # A doctor cannot approve themselves. Same stance as `role` on /register.
    editable = {
        key: value
        for key, value in body.items()
        if key in Doctor.REVIEWED_FIELDS + Doctor.OPERATIONAL_FIELDS
    }

    try:
        payload = validate_doctor(editable, partial=True)
    except ValidationError as error:
        return jsonify(
            {"error": "Please correct the highlighted fields", "fields": error.errors}
        ), 400

    changed = _changed_reviewed_fields(doctor, payload)

    specialty_name = payload.pop("specialty", None)
    if specialty_name:
        doctor.specialty = Specialty.get_or_create(specialty_name)
    for field, value in payload.items():
        setattr(doctor, field, value)

    if changed and doctor.approval_status == Doctor.STATUS_APPROVED:
        doctor.approval_status = Doctor.STATUS_PENDING
        labels = [FIELD_LABELS.get(field, field) for field in changed]
        doctor.pending_reason = (
            "You changed your " + _join(labels) + ", so your profile is being reviewed again."
        )

    db.session.commit()
    return jsonify(doctor.to_dict(include_availability=True))


def _join(items: list[str]) -> str:
    """`[a, b, c]` -> `a, b and c`."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
