"""Appointment booking endpoints.

Orchestration only. Slot arithmetic lives in `services/scheduling.py`, which
has no database and no request, so the awkward cases are unit-tested rather
than exercised through HTTP.

Payment is the next milestone. A booking made here holds the slot with
`status = pending_payment` and `payment_status = unpaid`; the payments module
takes it from there without changing this contract.
"""

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models.appointment import Appointment
from ...models.doctor import Doctor
from ...services import scheduling
from ...utils.security import current_user, login_required
from ..payments.routes import release_expired_holds

appointments_bp = Blueprint("appointments", __name__, url_prefix="/api")

HISTORY_LIMIT = 200


def _horizon_days() -> int:
    from flask import current_app

    return int(current_app.config.get("APPOINTMENT_HORIZON_DAYS", scheduling.DEFAULT_HORIZON_DAYS))


def _approved_doctor(doctor_id: int) -> Doctor | None:
    return Doctor.query.filter_by(id=doctor_id, approval_status=Doctor.STATUS_APPROVED).first()


def _taken_slots(doctor_id: int, on) -> set[str]:
    """Times already held for that doctor on that date.

    Cancelled bookings free their slot, which is the whole point of letting a
    patient cancel. They are excluded from the unique constraint by being
    deleted rather than kept - see `cancel_appointment`.
    """
    start = scheduling.combine(on, datetime.min.time())
    end = start.replace(hour=23, minute=59, second=59)
    rows = (
        db.session.query(Appointment.scheduled_for)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_for >= start,
            Appointment.scheduled_for <= end,
            Appointment.status != Appointment.STATUS_CANCELLED,
        )
        .all()
    )
    return {row[0].strftime("%H:%M") for row in rows}


# ------------------------------------------------------------------- routes


@appointments_bp.get("/doctors/<int:doctor_id>/slots")
def doctor_slots(doctor_id: int):
    """Bookable slots for one doctor on one date.

    Public and read-only. The prototype's equivalent wrote 56 availability
    rows when a day had none, which made an unauthenticated GET a way to grow
    the database; this derives everything and writes nothing.
    """
    doctor = _approved_doctor(doctor_id)
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    on = scheduling.parse_date(request.args.get("date"))
    if on is None:
        return jsonify({"error": "A date in YYYY-MM-DD format is required"}), 400

    # Slots held by a checkout nobody finished go back on sale here, which is
    # the moment the answer actually matters.
    release_expired_holds()

    now = scheduling.today_utc()
    reason = scheduling.bookable_reason(on, now, _horizon_days())
    if reason:
        return jsonify({"date": on.isoformat(), "slots": [], "bookable": False, "message": reason})

    slot_times = scheduling.slot_times_for_day(doctor.availability, on.weekday())
    if not slot_times:
        return jsonify(
            {
                "date": on.isoformat(),
                "slots": [],
                "bookable": False,
                "message": f"{doctor.name} does not consult on {on.strftime('%A')}s.",
            }
        )

    slots = scheduling.build_slots(
        slot_times,
        _taken_slots(doctor.id, on),
        on,
        datetime.now(UTC).replace(tzinfo=None),
    )
    return jsonify({"date": on.isoformat(), "slots": slots, "bookable": True, "message": None})


@appointments_bp.post("/appointments")
@login_required
def create_appointment():
    user = current_user()
    data = request.get_json(silent=True) or {}

    try:
        doctor_id = int(data.get("doctor_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "A doctor must be selected"}), 400

    doctor = _approved_doctor(doctor_id)
    if doctor is None:
        return jsonify({"error": "This doctor is not available for booking"}), 404

    release_expired_holds()

    on = scheduling.parse_date(data.get("date"))
    at = scheduling.parse_time(data.get("time"))
    if on is None or at is None:
        return jsonify({"error": "Please choose a valid date and time"}), 400

    reason_text = " ".join(str(data.get("reason") or "").split())
    if not reason_text:
        return jsonify({"error": "Please describe the reason for the visit"}), 400
    if len(reason_text) > Appointment.MAX_REASON_LENGTH:
        return jsonify(
            {"error": f"Please keep the reason under {Appointment.MAX_REASON_LENGTH} characters"}
        ), 400

    blocked = scheduling.bookable_reason(on, scheduling.today_utc(), _horizon_days())
    if blocked:
        return jsonify({"error": blocked}), 400

    slot_times = scheduling.slot_times_for_day(doctor.availability, on.weekday())
    if at.strftime("%H:%M") not in slot_times:
        return jsonify({"error": "This doctor does not consult at the selected time"}), 400

    scheduled_for = scheduling.combine(on, at)
    if scheduled_for <= datetime.now(UTC).replace(tzinfo=None):
        return jsonify({"error": "That time has already passed"}), 400

    appointment = Appointment(
        user_id=user.id,
        doctor_id=doctor.id,
        scheduled_for=scheduled_for,
        reason=reason_text,
        slot_key=Appointment.build_slot_key(scheduled_for),
        status=Appointment.STATUS_PENDING_PAYMENT,
        payment_status=Appointment.PAYMENT_UNPAID,
        fee_at_booking=doctor.fee,
    )
    db.session.add(appointment)

    try:
        db.session.commit()
    except IntegrityError:
        # Two patients submitting the same slot at the same moment both pass
        # any check we could do beforehand. The unique constraint is what
        # actually decides, and the loser is told so here.
        db.session.rollback()
        return jsonify({"error": "That slot has just been taken. Please choose another."}), 409

    return jsonify(appointment.to_dict()), 201


@appointments_bp.get("/appointments")
@login_required
def list_appointments():
    """A patient sees only their own bookings; an admin sees all."""
    user = current_user()
    query = Appointment.query
    if user.role != user.ROLE_ADMIN:
        query = query.filter_by(user_id=user.id)

    rows = query.order_by(Appointment.scheduled_for.desc()).limit(HISTORY_LIMIT).all()
    return jsonify([appointment.to_dict() for appointment in rows])


@appointments_bp.get("/appointments/<int:appointment_id>")
@login_required
def get_appointment(appointment_id: int):
    user = current_user()
    appointment = db.session.get(Appointment, appointment_id)
    # Someone else's appointment is reported as missing rather than forbidden,
    # so the endpoint cannot be used to discover which ids exist.
    if appointment is None or (appointment.user_id != user.id and user.role != user.ROLE_ADMIN):
        return jsonify({"error": "Appointment not found"}), 404
    return jsonify(appointment.to_dict())


@appointments_bp.post("/appointments/<int:appointment_id>/cancel")
@login_required
def cancel_appointment(appointment_id: int):
    user = current_user()
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.user_id != user.id:
        return jsonify({"error": "Appointment not found"}), 404

    if appointment.is_cancelled:
        return jsonify(appointment.to_dict())
    if appointment.is_paid:
        return jsonify({"error": "A paid appointment cannot be cancelled here"}), 400
    if appointment.is_past:
        return jsonify({"error": "A past appointment cannot be cancelled"}), 400

    appointment.status = Appointment.STATUS_CANCELLED
    appointment.cancelled_at = datetime.now(UTC)
    # The row stays for the patient's history, but the slot goes back on sale.
    appointment.release_slot()
    db.session.commit()
    return jsonify(appointment.to_dict())
