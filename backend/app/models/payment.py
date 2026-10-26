"""Payment attempt records.

The prototype kept `transaction_id` and `payment_method` on the appointment
itself, so retrying a failed payment overwrote the previous attempt. When
something went wrong there was nothing left to look at - and "what actually
happened to this patient's money" is the one question a payment system has to
be able to answer.

One row per attempt. Nothing here is ever deleted or overwritten; a retry
creates a new row.
"""

from datetime import UTC, datetime

from ..extensions import db


class PaymentAttempt(db.Model):
    __tablename__ = "payment_attempts"

    STATUS_INITIATED = "initiated"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    #: Which channel confirmed it. A payment settled by IPN was confirmed
    #: server-to-server; one settled by redirect passed through the patient's
    #: browser. Worth being able to tell apart when reconciling.
    VIA_REDIRECT = "redirect"
    VIA_IPN = "ipn"

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointments.id"), nullable=False, index=True
    )

    transaction_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default="BDT", nullable=False)

    status = db.Column(db.String(20), default=STATUS_INITIATED, nullable=False, index=True)
    #: Why an attempt was refused, in the words shown to the patient. Written
    #: for every rejection, including the ones that look like an attack.
    failure_reason = db.Column(db.String(300), nullable=True)

    session_key = db.Column(db.String(120), nullable=True)
    val_id = db.Column(db.String(120), nullable=True)
    bank_tran_id = db.Column(db.String(120), nullable=True)
    card_type = db.Column(db.String(80), nullable=True)
    settled_via = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    settled_at = db.Column(db.DateTime, nullable=True)

    appointment = db.relationship(
        "Appointment", backref=db.backref("payment_attempts", lazy="dynamic")
    )

    @property
    def is_settled(self) -> bool:
        return self.status == self.STATUS_PAID

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "card_type": self.card_type,
            "settled_via": self.settled_via,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
        }

    def __repr__(self) -> str:
        return f"<PaymentAttempt {self.transaction_id} {self.status}>"
