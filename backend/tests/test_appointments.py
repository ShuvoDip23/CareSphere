"""Booking API. Each test names the prototype defect it guards against."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import Doctor, DoctorAvailability, Specialty
from app.models.user import User


def _next_weekday(weekday: int) -> datetime:
    """The next occurrence of that weekday, always in the future."""
    today = datetime.now(UTC).replace(tzinfo=None)
    ahead = (weekday - today.weekday()) % 7
    return (today + timedelta(days=ahead or 7)).replace(hour=0, minute=0, second=0, microsecond=0)


@pytest.fixture
def clinic(app):
    specialty = Specialty.get_or_create("Cardiologist")
    db.session.flush()

    doctor = Doctor(
        name="Dr. Anwar Hossain",
        specialty=specialty,
        hospital="Padma Heart Centre",
        location="Laxmipur, Rajshahi",
        phone="+8801711000101",
        fee=1500,
        approval_status=Doctor.STATUS_APPROVED,
    )
    unapproved = Doctor(
        name="Dr. Pending Approval",
        specialty=specialty,
        hospital="Barind Clinic",
        location="Shaheb Bazar, Rajshahi",
        phone="+8801711000199",
        fee=900,
        approval_status=Doctor.STATUS_PENDING,
    )
    db.session.add_all([doctor, unapproved])
    db.session.flush()

    # Consulting on every weekday, 09:00-12:00 in 30-minute slots.
    for day in range(7):
        db.session.add(
            DoctorAvailability(
                doctor_id=doctor.id,
                day_of_week=day,
                start_time="09:00",
                end_time="12:00",
                slot_minutes=30,
            )
        )
    db.session.commit()
    return {"doctor": doctor, "unapproved": unapproved, "date": _next_weekday(2)}


@pytest.fixture
def signed_in(client, patient):
    client.post("/api/login", json={"email": patient.email, "password": "correct-horse"})
    return patient


def _book(client, clinic, time="09:00", reason="Chest discomfort when walking"):
    return client.post(
        "/api/appointments",
        json={
            "doctor_id": clinic["doctor"].id,
            "date": clinic["date"].strftime("%Y-%m-%d"),
            "time": time,
            "reason": reason,
        },
    )


# ------------------------------------------------------------------ slots


def test_slots_are_derived_not_stored(client, clinic):
    """The prototype inserted 56 rows on this GET. Nothing may be written."""
    before = Appointment.query.count()
    response = client.get(
        f"/api/doctors/{clinic['doctor'].id}/slots",
        query_string={"date": clinic["date"].strftime("%Y-%m-%d")},
    )
    assert response.status_code == 200
    assert [slot["time"] for slot in response.get_json()["slots"]][:3] == [
        "09:00",
        "09:30",
        "10:00",
    ]
    assert Appointment.query.count() == before


def test_slots_for_an_unapproved_doctor_are_not_found(client, clinic):
    response = client.get(
        f"/api/doctors/{clinic['unapproved'].id}/slots",
        query_string={"date": clinic["date"].strftime("%Y-%m-%d")},
    )
    assert response.status_code == 404


def test_a_booked_slot_is_reported_as_taken(client, clinic, signed_in):
    _book(client, clinic, time="09:30")
    response = client.get(
        f"/api/doctors/{clinic['doctor'].id}/slots",
        query_string={"date": clinic["date"].strftime("%Y-%m-%d")},
    )
    taken = [slot for slot in response.get_json()["slots"] if slot["is_booked"]]
    assert [slot["time"] for slot in taken] == ["09:30"]


# ---------------------------------------------------------------- booking


def test_booking_requires_login(client, clinic):
    assert _book(client, clinic).status_code == 401


def test_a_valid_booking_holds_the_slot_unpaid(client, clinic, signed_in):
    response = _book(client, clinic)
    assert response.status_code == 201

    body = response.get_json()
    assert body["status"] == Appointment.STATUS_PENDING_PAYMENT
    assert body["payment_status"] == Appointment.PAYMENT_UNPAID
    assert body["time"] == "09:00"
    assert body["doctor"]["name"] == "Dr. Anwar Hossain"


def test_a_time_outside_the_doctors_window_is_refused(client, clinic, signed_in):
    """14:00 is not in 09:00-12:00, so it must not become an appointment."""
    response = _book(client, clinic, time="14:00")
    assert response.status_code == 400
    assert Appointment.query.count() == 0


def test_a_time_that_is_not_a_slot_boundary_is_refused(client, clinic, signed_in):
    """09:17 falls inside the window but is not a slot the doctor offers."""
    assert _book(client, clinic, time="09:17").status_code == 400


def test_a_past_date_is_refused(client, clinic, signed_in):
    yesterday = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    response = client.post(
        "/api/appointments",
        json={
            "doctor_id": clinic["doctor"].id,
            "date": yesterday.strftime("%Y-%m-%d"),
            "time": "09:00",
            "reason": "Follow-up",
        },
    )
    assert response.status_code == 400


def test_an_unapproved_doctor_cannot_be_booked(client, clinic, signed_in):
    response = client.post(
        "/api/appointments",
        json={
            "doctor_id": clinic["unapproved"].id,
            "date": clinic["date"].strftime("%Y-%m-%d"),
            "time": "09:00",
            "reason": "Consultation",
        },
    )
    assert response.status_code == 404


def test_a_reason_is_required(client, clinic, signed_in):
    assert _book(client, clinic, reason="   ").status_code == 400


def test_double_booking_is_refused(client, clinic, signed_in):
    assert _book(client, clinic).status_code == 201
    assert _book(client, clinic).status_code == 409
    assert Appointment.query.count() == 1


def test_the_database_itself_rejects_a_duplicate_slot(app, clinic, patient):
    """The check-then-insert in the prototype was a race. This is the backstop.

    Two requests arriving together both pass any application-level check, so
    the constraint has to exist in the schema - not just in the handler.
    """
    when = clinic["date"].replace(hour=9)
    for _ in range(2):
        db.session.add(
            Appointment(
                user_id=patient.id,
                doctor_id=clinic["doctor"].id,
                scheduled_for=when,
                slot_key=Appointment.build_slot_key(when),
                reason="Duplicate",
                fee_at_booking=1500,
            )
        )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_the_fee_is_frozen_at_booking_time(client, clinic, signed_in):
    """Payment validation compares against this, not the doctor's live fee.

    In the prototype an admin editing the fee mid-flow made every in-flight
    payment fail the amount check.
    """
    _book(client, clinic)
    clinic["doctor"].fee = 2500
    db.session.commit()

    appointment = Appointment.query.one()
    assert float(appointment.fee_at_booking) == 1500.0


# ------------------------------------------------------- listing & privacy


def test_sessions_are_private_to_their_owner(client, clinic, signed_in, app):
    _book(client, clinic)
    appointment_id = Appointment.query.one().id

    other = User(email="someone.else@example.com", name="Other Patient")
    other.set_password("correct-horse")
    db.session.add(other)
    db.session.commit()

    client.post("/api/logout")
    client.post("/api/login", json={"email": other.email, "password": "correct-horse"})

    assert client.get("/api/appointments").get_json() == []
    # 404 rather than 403, so ids cannot be probed.
    assert client.get(f"/api/appointments/{appointment_id}").status_code == 404


def test_an_admin_sees_every_appointment(client, clinic, signed_in, app):
    _book(client, clinic)

    admin = User(email="admin@example.com", name="Admin", role=User.ROLE_ADMIN)
    admin.set_password("correct-horse")
    db.session.add(admin)
    db.session.commit()

    client.post("/api/logout")
    client.post("/api/login", json={"email": admin.email, "password": "correct-horse"})
    assert len(client.get("/api/appointments").get_json()) == 1


# ------------------------------------------------------------ cancellation


def test_cancelling_releases_the_slot_for_someone_else(client, clinic, signed_in):
    appointment_id = _book(client, clinic).get_json()["id"]
    assert client.post(f"/api/appointments/{appointment_id}/cancel").status_code == 200

    # The row survives for the patient's history...
    cancelled = db.session.get(Appointment, appointment_id)
    assert cancelled.status == Appointment.STATUS_CANCELLED
    assert cancelled.slot_key is None

    # ...but the slot is bookable again.
    assert _book(client, clinic).status_code == 201


def test_a_paid_appointment_cannot_be_cancelled_here(client, clinic, signed_in):
    appointment_id = _book(client, clinic).get_json()["id"]
    appointment = db.session.get(Appointment, appointment_id)
    appointment.payment_status = Appointment.PAYMENT_PAID
    db.session.commit()

    response = client.post(f"/api/appointments/{appointment_id}/cancel")
    assert response.status_code == 400


def test_someone_elses_appointment_cannot_be_cancelled(client, clinic, signed_in):
    appointment_id = _book(client, clinic).get_json()["id"]

    other = User(email="intruder@example.com", name="Intruder")
    other.set_password("correct-horse")
    db.session.add(other)
    db.session.commit()

    client.post("/api/logout")
    client.post("/api/login", json={"email": other.email, "password": "correct-horse"})

    assert client.post(f"/api/appointments/{appointment_id}/cancel").status_code == 404
    assert db.session.get(Appointment, appointment_id).status == (
        Appointment.STATUS_PENDING_PAYMENT
    )
