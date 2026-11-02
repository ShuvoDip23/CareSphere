"""In-app notification inbox."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

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

    @classmethod
    def enqueue(cls, patient_id: int, *, kind: str, title: str, message: str, dedupe_key=None):
        """Add a notification, skipping it if `dedupe_key` is already taken.

        `dedupe_key` is UNIQUE, which is the right way to make "notify once"
        a guarantee rather than a hope. But a UNIQUE constraint *raises* on a
        duplicate, and every caller here sits inside something that matters
        more than the notification: a settled payment, a loaded schedule.
        Failing those to avoid writing a second copy of a message is the wrong
        trade, so the duplicate is swallowed instead.

        The insert runs inside a SAVEPOINT, so a rejected duplicate rolls back
        only itself. Without that, the IntegrityError would poison the whole
        transaction and take the payment down with it anyway.

        Returns the row, or None when an identical one already existed.
        """
        row = cls(
            patient_id=patient_id, kind=kind, title=title, message=message, dedupe_key=dedupe_key
        )
        if dedupe_key is None:
            db.session.add(row)
            return row

        try:
            with db.session.begin_nested():
                db.session.add(row)
                db.session.flush()
        except IntegrityError:
            return None
        return row

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "message": self.message,
            "read": self.read_at is not None,
            "created_at": self.created_at.isoformat(),
        }
