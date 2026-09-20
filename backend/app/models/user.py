"""User account model."""

from datetime import UTC, datetime

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(db.Model):
    __tablename__ = "users"

    ROLE_PATIENT = "patient"
    ROLE_DOCTOR = "doctor"
    ROLE_PROVIDER = "provider"  # blood bank / ambulance operator (proposal 4.1)
    ROLE_ADMIN = "admin"
    ROLES = (ROLE_PATIENT, ROLE_DOCTOR, ROLE_PROVIDER, ROLE_ADMIN)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default=ROLE_PATIENT, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    def set_password(self, raw_password: str) -> None:
        """Hash with PBKDF2 via Werkzeug.

        The previous implementation used a bare hashlib.sha256 of the password
        with no salt and no work factor, which is trivially reversible with a
        rainbow table. See tests/test_auth.py::test_password_is_not_sha256.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role or self.ROLE_PATIENT,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} ({self.role})>"
