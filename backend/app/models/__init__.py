"""Model package.

Every model must be imported here so SQLAlchemy registers it and Flask-Migrate
can autogenerate migrations for it. Add yours in the PR that introduces it.
"""

from .chat import ChatMessage, ChatSession
from .doctor import Doctor, DoctorAvailability, Specialty
from .user import User

__all__ = [
    "User",
    "Specialty",
    "Doctor",
    "DoctorAvailability",
    "ChatSession",
    "ChatMessage",
]

# Week 3 - Shuvo  from .appointment import Appointment
# Week 6 - Shuvo  from .emergency import EmergencyProvider, EmergencyAlert
# Week 4 - Ifti   from .donor import BloodDonor, DonorRequest
# Week 6 - Ifti   from .ambulance import AmbulanceProvider
# Week 5 - Jit    from .prescription import Prescription, PrescriptionItem
# Week 7 - Jit    from .reminder import MedicationReminder
