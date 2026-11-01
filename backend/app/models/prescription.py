"""Patient-verified prescription records."""
from datetime import UTC, datetime

from ..extensions import db


class Prescription(db.Model):
    __tablename__ = "prescriptions"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    raw_text = db.Column(db.Text, nullable=False)
    items = db.Column(db.JSON, nullable=False, default=list)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    patient = db.relationship("User", backref=db.backref("prescriptions", lazy="dynamic"))

    def to_dict(self):
        return {"id": self.id, "raw_text": self.raw_text, "items": self.items or [],
                "verified": self.verified, "created_at": self.created_at.isoformat()}
