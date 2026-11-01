"""In-app notification inbox."""
from datetime import UTC, datetime
from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False, default="system")
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    dedupe_key = db.Column(db.String(180), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "title": self.title,
                "message": self.message, "read": self.read_at is not None,
                "created_at": self.created_at.isoformat()}
