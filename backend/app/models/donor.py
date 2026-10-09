"""Blood donor and contact request models."""

from datetime import UTC, date, datetime

from ..extensions import db

BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
URGENCY_LEVELS = ("emergency", "urgent", "routine")
REQUEST_STATUSES = ("pending", "accepted", "declined", "fulfilled")


class BloodDonor(db.Model):
    __tablename__ = "blood_donors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Confidential identity fields - NEVER exposed via public endpoints
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)

    # Public demographic & clinical fields
    blood_group = db.Column(db.String(5), nullable=False, index=True)
    area = db.Column(db.String(120), nullable=False, index=True)
    hospital_near = db.Column(db.String(200), nullable=True)
    last_donation_date = db.Column(db.Date, nullable=True)
    donations_count = db.Column(db.Integer, default=0, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    requests = db.relationship(
        "DonorRequest",
        back_populates="donor",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def display_id(self) -> str:
        return f"BD-{self.id}"

    @property
    def days_ago(self) -> int | None:
        if not self.last_donation_date:
            return None
        return (date.today() - self.last_donation_date).days

    @property
    def status(self) -> str:
        if not self.is_available:
            return "unavailable"
        if self.days_ago is not None and self.days_ago < 90:
            return "eligible_soon"
        return "available"

    @property
    def status_label(self) -> str:
        if not self.is_available:
            return "Unavailable"
        if self.last_donation_date is None:
            return "Available (New)"
        days = self.days_ago
        if days is not None and days < 90:
            remaining = 90 - days
            return f"Eligible in {remaining} day{'s' if remaining != 1 else ''}"
        return "Available Now"

    @property
    def badge_class(self) -> str:
        if not self.is_available:
            return "badge-muted"
        if self.status == "eligible_soon":
            return "badge-warn"
        return "badge-ok"

    @property
    def last_donation_formatted(self) -> str:
        if not self.last_donation_date:
            return "First-time donor"
        return self.last_donation_date.strftime("%d %b %Y")

    def to_dict(self, public: bool = True) -> dict:
        """Serialize donor record.

        Privacy guarantee: When public=True (default), identity fields ('name', 'phone')
        are completely omitted.
        """
        payload = {
            "id": self.id,
            "display_id": self.display_id,
            "blood_group": self.blood_group,
            "area": self.area,
            "hospital_near": self.hospital_near,
            "last_donation": self.last_donation_formatted,
            "last_donation_date": (
                self.last_donation_date.isoformat() if self.last_donation_date else None
            ),
            "days_ago": self.days_ago,
            "donations_count": self.donations_count,
            "status": self.status,
            "status_label": self.status_label,
            "badge_class": self.badge_class,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if not public:
            payload["name"] = self.name
            payload["phone"] = self.phone
            payload["is_available"] = self.is_available
            payload["user_id"] = self.user_id
        return payload


class DonorRequest(db.Model):
    __tablename__ = "donor_requests"

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("blood_donors.id"), nullable=False, index=True)
    patient_name = db.Column(db.String(100), nullable=False)
    hospital = db.Column(db.String(200), nullable=False)
    units = db.Column(db.Integer, default=1, nullable=False)
    urgency = db.Column(db.String(20), default="emergency", nullable=False)
    requester_phone = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    donor = db.relationship("BloodDonor", back_populates="requests")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "donor_id": self.donor_id,
            "donor_display_id": self.donor.display_id if self.donor else f"BD-{self.donor_id}",
            "donor_blood_group": self.donor.blood_group if self.donor else None,
            "patient_name": self.patient_name,
            "hospital": self.hospital,
            "units": self.units,
            "urgency": self.urgency,
            "requester_phone": self.requester_phone,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
