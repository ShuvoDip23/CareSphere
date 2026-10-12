"""AI health assistant conversation models."""

import json
from datetime import UTC, datetime

from ..extensions import db


class ChatSession(db.Model):
    """One triage conversation, from first symptom to recommendation."""

    __tablename__ = "chat_sessions"

    STEP_COLLECTING = "collecting_symptoms"
    STEP_QUESTIONING = "questioning"
    STEP_COMPLETE = "complete"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True)

    current_step = db.Column(db.String(32), default=STEP_COLLECTING, nullable=False)
    state_json = db.Column(db.Text, default="{}", nullable=False)

    recommended_specialty = db.Column(db.String(80), nullable=True)
    urgency = db.Column(db.String(20), nullable=True)

    started_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("chat_sessions", lazy="dynamic"))
    messages = db.relationship(
        "ChatMessage",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )

    @property
    def state(self) -> dict:
        try:
            value = json.loads(self.state_json or "{}")
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    @state.setter
    def state(self, value: dict) -> None:
        self.state_json = json.dumps(value or {})

    @property
    def is_complete(self) -> bool:
        return self.current_step == self.STEP_COMPLETE

    def first_symptom(self) -> str:
        """The opening complaint, used as a label in the history list."""
        return self.state.get("symptoms") or "New assessment"

    def to_dict(self, include_messages: bool = False) -> dict:
        payload = {
            "id": self.public_id,
            "step": self.current_step,
            "is_complete": self.is_complete,
            "summary": self.first_symptom(),
            "recommended_specialty": self.recommended_specialty,
            "urgency": self.urgency,
            "message_count": len(self.messages),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
        if include_messages:
            payload["messages"] = [message.to_dict() for message in self.messages]
        return payload


class ChatMessage(db.Model):
    """A single turn. Bot turns carry structured data the UI renders directly.

    The prototype stored a markdown blob and re-parsed it in JavaScript with
    regular expressions; any wording change in a prompt silently broke the
    rendering. Structured data in `data_json` removes that coupling.
    """

    __tablename__ = "chat_messages"

    SENDER_USER = "user"
    SENDER_BOT = "bot"

    KIND_TEXT = "text"
    KIND_QUESTION = "question"
    KIND_RECOMMENDATION = "recommendation"
    KIND_EMERGENCY = "emergency"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    sender = db.Column(db.String(10), nullable=False)
    kind = db.Column(db.String(20), default=KIND_TEXT, nullable=False)
    text = db.Column(db.Text, nullable=False)
    data_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    session = db.relationship("ChatSession", back_populates="messages")

    @property
    def data(self) -> dict | None:
        if not self.data_json:
            return None
        try:
            return json.loads(self.data_json)
        except (TypeError, ValueError):
            return None

    @data.setter
    def data(self, value: dict | None) -> None:
        self.data_json = json.dumps(value) if value else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "kind": self.kind,
            "text": self.text,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
