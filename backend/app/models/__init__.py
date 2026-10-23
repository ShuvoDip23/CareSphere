"""Model package.

Every model must be imported here so SQLAlchemy registers it and Flask-Migrate
can autogenerate migrations for it. Add yours in the PR that introduces it.
"""

from .appointment import Appointment
from .chat import ChatMessage, ChatSession
from .doctor import Doctor, DoctorAvailability, Specialty
from .donor import BloodDonor, DonorRequest
from .user import User

__all__ = [
    "User",
    "Specialty",
    "Doctor",
    "DoctorAvailability",
    "BloodDonor",
    "DonorRequest",
    "ChatSession",
    "ChatMessage",
    "Appointment",
]

# Week 4 - Shuvo  from .payment import PaymentAttempt
# Week 6 - Shuvo  from .emergency import EmergencyProvider, EmergencyAlert
# Week 6 - Ifti   from .ambulance import AmbulanceProvider
# Week 5 - Jit    from .prescription import Prescription, PrescriptionItem
# Week 7 - Jit    from .reminder import MedicationReminder
