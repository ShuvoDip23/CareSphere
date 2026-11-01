"""Patient-owned medication plans and dose tracking."""
from datetime import date, datetime, timedelta
from flask import Blueprint, jsonify, request
from ...extensions import db
from ...models.notification import Notification
from ...models.prescription import Prescription
from ...models.reminder import MedicationLog, MedicationReminder
from ...utils.security import patient_required, current_user

reminders_bp = Blueprint("reminders", __name__, url_prefix="/api/reminders")


def _owned(reminder_id):
    return MedicationReminder.query.filter_by(id=reminder_id, patient_id=current_user().id).first()


def _payload(data, existing=None):
    name = str(data.get("medicine_name", existing.medicine_name if existing else "") or "").strip()
    dosage = str(data.get("dosage", existing.dosage if existing else "") or "").strip()
    frequency = str(data.get("frequency", existing.frequency if existing else "") or "").strip()
    times = data.get("times", existing.times if existing else [])
    start = data.get("start_date", existing.start_date.isoformat() if existing else date.today().isoformat())
    end = data.get("end_date", existing.end_date.isoformat() if existing and existing.end_date else None)
    instructions = str(data.get("instructions", existing.instructions if existing else "") or "").strip()
    if not name or len(name) > 160 or not dosage or len(dosage) > 120 or not frequency or len(frequency) > 120:
        raise ValueError("Medicine name, dosage and frequency are required")
    if not isinstance(times, list) or not times or len(times) > 12:
        raise ValueError("Provide between 1 and 12 reminder times")
    try:
        times = sorted(set(datetime.strptime(str(t), "%H:%M").strftime("%H:%M") for t in times))
        start_date = date.fromisoformat(str(start))
        end_date = date.fromisoformat(str(end)) if end else None
    except (ValueError, TypeError):
        raise ValueError("Dates must use YYYY-MM-DD and times must use HH:MM")
    if end_date and end_date < start_date:
        raise ValueError("End date cannot be before start date")
    return dict(medicine_name=name, dosage=dosage, frequency=frequency, times=times,
                start_date=start_date, end_date=end_date, instructions=instructions[:500])


@reminders_bp.get("")
@patient_required
def list_reminders():
    rows = MedicationReminder.query.filter_by(patient_id=current_user().id).order_by(MedicationReminder.active.desc(), MedicationReminder.medicine_name).all()
    return jsonify({"reminders": [r.to_dict() for r in rows]})


@reminders_bp.post("")
@patient_required
def create_reminder():
    data = request.get_json(silent=True) or {}
    try:
        values = _payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    prescription_id = data.get("prescription_id")
    if prescription_id is not None:
        prescription = Prescription.query.filter_by(id=prescription_id, patient_id=current_user().id, verified=True).first()
        if not prescription:
            return jsonify({"error": "Verified prescription not found"}), 404
    row = MedicationReminder(patient_id=current_user().id, prescription_id=prescription_id, **values)
    db.session.add(row)
    db.session.commit()
    return jsonify({"reminder": row.to_dict()}), 201


@reminders_bp.patch("/<int:reminder_id>")
@patient_required
def update_reminder(reminder_id):
    row = _owned(reminder_id)
    if not row:
        return jsonify({"error": "Reminder not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        values = _payload(data, row)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    for key, value in values.items():
        setattr(row, key, value)
    if "active" in data:
        row.active = bool(data["active"])
    db.session.commit()
    return jsonify({"reminder": row.to_dict()})


@reminders_bp.delete("/<int:reminder_id>")
@patient_required
def delete_reminder(reminder_id):
    row = _owned(reminder_id)
    if not row:
        return jsonify({"error": "Reminder not found"}), 404
    MedicationLog.query.filter_by(reminder_id=row.id).delete()
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Reminder deleted"})


@reminders_bp.get("/today")
@patient_required
def today_schedule():
    today = date.today()
    now = datetime.now()
    rows = MedicationReminder.query.filter_by(patient_id=current_user().id, active=True).all()
    entries = []
    for row in rows:
        if today < row.start_date or (row.end_date and today > row.end_date):
            continue
        for time in row.times or []:
            scheduled = datetime.combine(today, datetime.strptime(time, "%H:%M").time())
            log = MedicationLog.query.filter_by(reminder_id=row.id, scheduled_for=scheduled).first()
            if log is None and scheduled < now - timedelta(minutes=30):
                log = MedicationLog(reminder_id=row.id, patient_id=current_user().id,
                                    scheduled_for=scheduled, status="missed")
                db.session.add(log)
                db.session.flush()
                db.session.add(Notification(patient_id=current_user().id, kind="missed_medication",
                    title="Medication may have been missed", message=f"{row.medicine_name} ({row.dosage}) was scheduled for {time}.",
                    dedupe_key=f"missed:{row.id}:{scheduled.isoformat()}"))
            elif log is None and scheduled <= now:
                db.session.add(Notification(patient_id=current_user().id, kind="medication_reminder",
                    title="Medication due", message=f"It's time for {row.medicine_name} ({row.dosage}).",
                    dedupe_key=f"due:{row.id}:{scheduled.isoformat()}"))
            entries.append({"reminder": row.to_dict(), "scheduled_for": scheduled.isoformat(),
                            "status": log.status if log else "upcoming", "log_id": log.id if log else None})
    db.session.commit()
    entries.sort(key=lambda e: e["scheduled_for"])
    return jsonify({"date": today.isoformat(), "schedule": entries})


@reminders_bp.post("/<int:reminder_id>/log")
@patient_required
def log_dose(reminder_id):
    row = _owned(reminder_id)
    if not row:
        return jsonify({"error": "Reminder not found"}), 404
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("taken", "skipped"):
        return jsonify({"error": "Status must be taken or skipped"}), 400
    try:
        scheduled = datetime.fromisoformat(str(data.get("scheduled_for")))
    except (ValueError, TypeError):
        return jsonify({"error": "A valid scheduled_for timestamp is required"}), 400
    if scheduled.date() < row.start_date or (row.end_date and scheduled.date() > row.end_date):
        return jsonify({"error": "Dose is outside this medication plan"}), 400
    if scheduled.strftime("%H:%M") not in (row.times or []):
        return jsonify({"error": "Dose time is not part of this medication plan"}), 400
    log = MedicationLog.query.filter_by(reminder_id=row.id, scheduled_for=scheduled).first()
    if log:
        log.status = status
        log.recorded_at = datetime.now()
    else:
        log = MedicationLog(reminder_id=row.id, patient_id=current_user().id,
                            scheduled_for=scheduled, status=status)
        db.session.add(log)
    db.session.commit()
    return jsonify({"log": log.to_dict()})


@reminders_bp.get("/history")
@patient_required
def history():
    logs = MedicationLog.query.filter_by(patient_id=current_user().id).order_by(MedicationLog.scheduled_for.desc()).limit(300).all()
    total = len(logs)
    taken = sum(1 for x in logs if x.status == "taken")
    return jsonify({"history": [x.to_dict() for x in logs], "statistics": {
        "total_recorded": total, "taken": taken, "skipped": sum(x.status == "skipped" for x in logs),
        "missed": sum(x.status == "missed" for x in logs),
        "adherence_percent": round(taken / total * 100) if total else 0}})
