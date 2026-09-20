"""Doctor directory models."""

import re
from datetime import UTC, datetime

from ..extensions import db

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def slugify(value: str) -> str:
    """`ENT Specialist` -> `ent-specialist`."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return cleaned.strip("-")


class Specialty(db.Model):
    """A medical specialty.

    The prototype stored the specialty as free text on each doctor row, which
    produced both "Cardiologist" and "Cardiology" in the same database - so
    filtering by one silently missed the other. Making it a table with a unique
    slug removes that whole class of bug.
    """

    __tablename__ = "specialties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(240), nullable=True)

    doctors = db.relationship("Doctor", back_populates="specialty", lazy="dynamic")

    @classmethod
    def get_or_create(cls, name: str) -> "Specialty":
        slug = slugify(name)
        existing = cls.query.filter_by(slug=slug).first()
        if existing:
            return existing
        specialty = cls(name=name.strip(), slug=slug)
        db.session.add(specialty)
        return specialty

    def to_dict(self, doctor_count: int | None = None) -> dict:
        payload = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
        }
        if doctor_count is not None:
            payload["doctor_count"] = doctor_count
        return payload


class Doctor(db.Model):
    __tablename__ = "doctors"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    specialty_id = db.Column(
        db.Integer, db.ForeignKey("specialties.id"), nullable=False, index=True
    )

    name = db.Column(db.String(120), nullable=False)
    qualification = db.Column(db.String(240), nullable=True)
    hospital = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    bio = db.Column(db.Text, nullable=True)

    fee = db.Column(db.Numeric(10, 2), nullable=False)
    rating = db.Column(db.Float, default=0.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    experience_years = db.Column(db.Integer, default=0, nullable=False)

    approval_status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False, index=True)
    rejection_note = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    specialty = db.relationship("Specialty", back_populates="doctors")
    availability = db.relationship(
        "DoctorAvailability",
        back_populates="doctor",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="DoctorAvailability.day_of_week",
    )

    @property
    def initials(self) -> str:
        stripped = re.sub(r"^(?:(?:Dr|Prof|Mr|Mrs|Ms|Md)\.?\s+)+", "", self.name, flags=re.I)
        parts = [part for part in stripped.split() if part]
        if not parts:
            return "DR"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def to_dict(self, include_availability: bool = False) -> dict:
        payload = {
            "id": self.id,
            "name": self.name,
            "initials": self.initials,
            "qualification": self.qualification,
            "hospital": self.hospital,
            "location": self.location,
            "phone": self.phone,
            "bio": self.bio,
            "fee": float(self.fee),
            "rating": round(self.rating or 0.0, 1),
            "review_count": self.review_count,
            "experience_years": self.experience_years,
            "approval_status": self.approval_status,
            "rejection_note": self.rejection_note,
            "specialty": self.specialty.to_dict() if self.specialty else None,
        }
        if include_availability:
            payload["availability"] = [slot.to_dict() for slot in self.availability]
        return payload


class DoctorAvailability(db.Model):
    """A recurring weekly consulting window.

    The prototype wrote one row per doctor per day per slot - 56 rows each,
    seeded lazily from inside a GET handler. Storing the window instead and
    deriving slots at booking time is both smaller and side-effect free.
    """

    __tablename__ = "doctor_availability"
    __table_args__ = (
        db.UniqueConstraint("doctor_id", "day_of_week", "start_time", name="uq_doctor_window"),
    )

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday
    start_time = db.Column(db.String(5), nullable=False)  # "09:00", 24-hour
    end_time = db.Column(db.String(5), nullable=False)
    slot_minutes = db.Column(db.Integer, default=30, nullable=False)

    doctor = db.relationship("Doctor", back_populates="availability")

    @property
    def day_name(self) -> str:
        return DAY_NAMES[self.day_of_week % 7]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day_of_week": self.day_of_week,
            "day_name": self.day_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "slot_minutes": self.slot_minutes,
        }
