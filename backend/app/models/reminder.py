"""Medication plans and explicitly confirmed dose history."""

from datetime import UTC, datetime

from ..extensions import db


class MedicationReminder(db.Model):
    __tablename__ = "medication_reminders"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"), nullable=True)
    medicine_name = db.Column(db.String(160), nullable=False)
    dosage = db.Column(db.String(120), nullable=False)
    frequency = db.Column(db.String(120), nullable=False)
    times = db.Column(db.JSON, nullable=False, default=list)
    instructions = db.Column(db.String(500), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    patient = db.relationship("User", backref=db.backref("medication_reminders", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "prescription_id": self.prescription_id,
            "medicine_name": self.medicine_name,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "times": self.times or [],
            "instructions": self.instructions,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "active": self.active,
        }


class MedicationLog(db.Model):
    __tablename__ = "medication_logs"
    __table_args__ = (db.UniqueConstraint("reminder_id", "scheduled_for", name="uq_med_log_slot"),)
    id = db.Column(db.Integer, primary_key=True)
    reminder_id = db.Column(
        db.Integer, db.ForeignKey("medication_reminders.id"), nullable=False, index=True
    )
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(12), nullable=False)  # taken / skipped / missed
    recorded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    reminder = db.relationship("MedicationReminder", backref=db.backref("logs", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "reminder_id": self.reminder_id,
            "scheduled_for": self.scheduled_for.isoformat(),
            "status": self.status,
            "recorded_at": self.recorded_at.isoformat(),
        }
