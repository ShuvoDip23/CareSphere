"""Appointment booking model.

Five things changed from the prototype, each because of a defect it caused:

1. `user_id` is a real foreign key. It was `db.String(100)` holding a
   stringified id, compared with `filter_by(user_id=str(session['user_id']))`.
   Nothing stopped an appointment pointing at a deleted account.
2. The slot is one `scheduled_for` datetime instead of `appointment_date` and
   `appointment_time` strings, so "is this in the past" is a comparison rather
   than two parses and a guess.
3. `fee_at_booking` snapshots the price. Payment validation compared the
   gateway amount against `appointment.doctor.fee`, so an admin editing the fee
   between booking and payment made every in-flight payment fail the check.
4. A unique constraint on (doctor_id, slot_key) makes double-booking
   impossible in the database. The prototype queried for a clash and then
   inserted - two requests arriving together both passed the check.
5. The patient's name is read through the relationship instead of being copied
   onto the row, so renaming an account no longer leaves stale names behind.
"""

from datetime import UTC, datetime

from ..extensions import db


class Appointment(db.Model):
    __tablename__ = "appointments"
    __table_args__ = (db.UniqueConstraint("doctor_id", "slot_key", name="uq_appointment_slot"),)

    # The slot is held but not yet paid for. Payment is the next milestone;
    # until then every booking rests here and can be cancelled freely.
    STATUS_PENDING_PAYMENT = "pending_payment"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"
    STATUS_NO_SHOW = "no_show"
    STATUSES = (
        STATUS_PENDING_PAYMENT,
        STATUS_CONFIRMED,
        STATUS_CANCELLED,
        STATUS_COMPLETED,
        STATUS_NO_SHOW,
    )
    #: What a doctor may set once the appointment time has passed.
    DOCTOR_OUTCOMES = (STATUS_COMPLETED, STATUS_NO_SHOW)

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_REFUNDED = "refunded"

    MAX_REASON_LENGTH = 500

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False, index=True)

    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    reason = db.Column(db.String(MAX_REASON_LENGTH), nullable=False)

    # "2026-11-03T09:00" while the slot is held, NULL once it is released.
    # Both SQLite and PostgreSQL treat NULLs as distinct in a UNIQUE
    # constraint, so clearing this frees the slot for someone else while the
    # cancelled row stays in the patient's history. A partial index would do
    # the same job but is spelled differently in every dialect.
    slot_key = db.Column(db.String(20), nullable=True)

    status = db.Column(db.String(20), default=STATUS_PENDING_PAYMENT, nullable=False, index=True)
    payment_status = db.Column(db.String(20), default=PAYMENT_UNPAID, nullable=False)

    # Snapshot, not a lookup. See note 3 above.
    fee_at_booking = db.Column(db.Numeric(10, 2), nullable=False)

    # Populated in the payments milestone. Nullable now so the column does not
    # need a second migration later.
    transaction_id = db.Column(db.String(64), nullable=True, unique=True)
    payment_method = db.Column(db.String(60), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    # A paid appointment cannot be cancelled in the app, because that would
    # leave the patient's money taken and nothing to show for it. They ask
    # instead, and an administrator handles the refund outside the system.
    refund_requested_at = db.Column(db.DateTime, nullable=True)
    refund_reason = db.Column(db.String(300), nullable=True)

    patient = db.relationship("User", backref=db.backref("appointments", lazy="dynamic"))
    doctor = db.relationship("Doctor", backref=db.backref("appointments", lazy="dynamic"))

    @staticmethod
    def build_slot_key(scheduled_for: datetime) -> str:
        return scheduled_for.strftime("%Y-%m-%dT%H:%M")

    def release_slot(self) -> None:
        """Hand the slot back so another patient can book it."""
        self.slot_key = None

    @property
    def is_cancelled(self) -> bool:
        return self.status == self.STATUS_CANCELLED

    @property
    def is_paid(self) -> bool:
        return self.payment_status == self.PAYMENT_PAID

    @property
    def is_past(self) -> bool:
        return self.scheduled_for < datetime.now(UTC).replace(tzinfo=None)

    @property
    def can_pay(self) -> bool:
        """Still unpaid, still upcoming, and the slot is still held."""
        return (
            not self.is_cancelled
            and not self.is_paid
            and not self.is_past
            and self.slot_key is not None
        )

    @property
    def can_cancel(self) -> bool:
        """Only a patient's own unpaid, future, live booking.

        Refunds are a payments concern and do not exist yet, so a paid
        appointment is deliberately not cancellable from here rather than
        being cancelled with the money left stranded.
        """
        return not self.is_cancelled and not self.is_paid and not self.is_past

    def to_dict(self, include_doctor: bool = True) -> dict:
        payload = {
            "id": self.id,
            "scheduled_for": self.scheduled_for.isoformat(),
            "date": self.scheduled_for.strftime("%Y-%m-%d"),
            "time": self.scheduled_for.strftime("%H:%M"),
            "reason": self.reason,
            "status": self.status,
            "payment_status": self.payment_status,
            "fee": float(self.fee_at_booking),
            "patient_name": self.patient.name if self.patient else None,
            "is_past": self.is_past,
            "can_cancel": self.can_cancel,
            "can_pay": self.can_pay,
            "refund_requested": self.refund_requested_at is not None,
            "refund_reason": self.refund_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_doctor and self.doctor is not None:
            payload["doctor"] = {
                "id": self.doctor.id,
                "name": self.doctor.name,
                "initials": self.doctor.initials,
                "hospital": self.doctor.hospital,
                "location": self.doctor.location,
                "phone": self.doctor.phone,
                "specialty": self.doctor.specialty.name if self.doctor.specialty else None,
            }
        return payload

    def __repr__(self) -> str:
        return f"<Appointment {self.id} doctor={self.doctor_id} at {self.scheduled_for}>"
