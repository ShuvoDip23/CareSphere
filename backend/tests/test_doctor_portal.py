"""The doctor's own view. The isolation tests are the point of this file."""

from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import Doctor, DoctorAvailability, Specialty
from app.models.user import User


def _make_doctor(name, email, specialty, approved=True):
    user = User(email=email, name=name, role=User.ROLE_DOCTOR)
    user.set_password("correct-horse")
    db.session.add(user)
    db.session.flush()

    doctor = Doctor(
        name=name,
        specialty=specialty,
        hospital="Padma Heart Centre",
        location="Laxmipur, Rajshahi",
        phone="+8801711000101",
        fee=1500,
        user_id=user.id,
        approval_status=Doctor.STATUS_APPROVED if approved else Doctor.STATUS_PENDING,
    )
    db.session.add(doctor)
    db.session.flush()
    db.session.add(
        DoctorAvailability(doctor_id=doctor.id, day_of_week=0, start_time="09:00", end_time="12:00")
    )
    return user, doctor


def _booking(doctor, patient, when, status=Appointment.STATUS_PENDING_PAYMENT):
    appointment = Appointment(
        user_id=patient.id,
        doctor_id=doctor.id,
        scheduled_for=when,
        slot_key=Appointment.build_slot_key(when),
        reason="Chest discomfort",
        status=status,
        fee_at_booking=doctor.fee,
    )
    db.session.add(appointment)
    db.session.flush()
    return appointment


@pytest.fixture
def clinic(app, patient):
    specialty = Specialty.get_or_create("Cardiologist")
    db.session.flush()

    mine_user, mine = _make_doctor("Dr. Anwar Hossain", "anwar@example.com", specialty)
    other_user, other = _make_doctor("Dr. Farhana Islam", "farhana@example.com", specialty)

    now = datetime.now(UTC).replace(tzinfo=None)
    data = {
        "doctor": mine,
        "doctor_user": mine_user,
        "other": other,
        "other_user": other_user,
        "patient": patient,
        "future": _booking(mine, patient, now + timedelta(days=3, hours=1)),
        "past": _booking(mine, patient, now - timedelta(days=3)),
        "theirs": _booking(other, patient, now + timedelta(days=4)),
    }
    db.session.commit()
    return data


@pytest.fixture
def as_doctor(client, clinic):
    client.post(
        "/api/login", json={"email": clinic["doctor_user"].email, "password": "correct-horse"}
    )
    return clinic


# ----------------------------------------------------------------- access


def test_a_patient_cannot_reach_the_doctor_portal(client, clinic, patient):
    client.post("/api/login", json={"email": patient.email, "password": "correct-horse"})
    assert client.get("/api/doctor/appointments").status_code == 403


def test_signed_out_is_rejected(client, clinic):
    assert client.get("/api/doctor/appointments").status_code == 401


def test_a_doctor_account_with_no_profile_gets_a_clear_answer(client, app):
    """Possible while linking is a CLI step. It must not be a 500."""
    user = User(email="unlinked@example.com", name="Dr. Unlinked", role=User.ROLE_DOCTOR)
    user.set_password("correct-horse")
    db.session.add(user)
    db.session.commit()

    client.post("/api/login", json={"email": user.email, "password": "correct-horse"})
    response = client.get("/api/doctor/appointments")
    assert response.status_code == 409
    assert "not linked" in response.get_json()["error"]


def test_a_pending_doctor_can_still_read_their_own_profile(client, app):
    """Reading your own rejection note is the reason the note exists."""
    specialty = Specialty.get_or_create("Dermatologist")
    db.session.flush()
    user, doctor = _make_doctor("Dr. Waiting", "waiting@example.com", specialty, approved=False)
    doctor.rejection_note = "Please attach your BMDC registration number."
    db.session.commit()

    client.post("/api/login", json={"email": user.email, "password": "correct-horse"})
    body = client.get("/api/doctor/me").get_json()
    assert body["approval_status"] == Doctor.STATUS_PENDING
    assert "BMDC" in body["rejection_note"]


# -------------------------------------------------------------- isolation


def test_a_doctor_sees_only_their_own_bookings(client, as_doctor):
    items = client.get("/api/doctor/appointments?scope=all").get_json()["items"]
    assert {item["id"] for item in items} == {as_doctor["future"].id, as_doctor["past"].id}
    assert as_doctor["theirs"].id not in {item["id"] for item in items}


def test_a_doctor_cannot_close_out_another_doctors_appointment(client, as_doctor):
    response = client.post(
        f"/api/doctor/appointments/{as_doctor['theirs'].id}/outcome",
        json={"status": Appointment.STATUS_COMPLETED},
    )
    # 404, not 403: the id must not be confirmable as real.
    assert response.status_code == 404
    assert db.session.get(Appointment, as_doctor["theirs"].id).status == (
        Appointment.STATUS_PENDING_PAYMENT
    )


def test_editing_availability_does_not_touch_another_doctor(client, as_doctor):
    before = DoctorAvailability.query.filter_by(doctor_id=as_doctor["other"].id).count()
    response = client.put(
        "/api/doctor/availability",
        json={"availability": [{"day_of_week": 2, "start_time": "15:00", "end_time": "18:00"}]},
    )
    assert response.status_code == 200
    assert DoctorAvailability.query.filter_by(doctor_id=as_doctor["other"].id).count() == before


# -------------------------------------------------------------- scoping


def test_today_scope_excludes_other_days(client, as_doctor, patient):
    now = datetime.now(UTC).replace(tzinfo=None)
    today = _booking(as_doctor["doctor"], patient, now.replace(hour=23, minute=30))
    db.session.commit()

    items = client.get("/api/doctor/appointments?scope=today").get_json()["items"]
    assert [item["id"] for item in items] == [today.id]


def test_upcoming_is_sorted_soonest_first(client, as_doctor, patient):
    now = datetime.now(UTC).replace(tzinfo=None)
    later = _booking(as_doctor["doctor"], patient, now + timedelta(days=10))
    db.session.commit()

    items = client.get("/api/doctor/appointments?scope=upcoming").get_json()["items"]
    ids = [item["id"] for item in items]
    assert ids.index(as_doctor["future"].id) < ids.index(later.id)


def test_an_unknown_scope_falls_back_to_all(client, as_doctor):
    body = client.get("/api/doctor/appointments?scope=nonsense").get_json()
    assert body["scope"] == "all"


# --------------------------------------------------------------- outcomes


def test_a_past_appointment_can_be_completed(client, as_doctor):
    response = client.post(
        f"/api/doctor/appointments/{as_doctor['past'].id}/outcome",
        json={"status": Appointment.STATUS_COMPLETED},
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == Appointment.STATUS_COMPLETED


def test_a_future_appointment_cannot_be_completed(client, as_doctor):
    """Otherwise a doctor could close out a visit that has not happened."""
    response = client.post(
        f"/api/doctor/appointments/{as_doctor['future'].id}/outcome",
        json={"status": Appointment.STATUS_COMPLETED},
    )
    assert response.status_code == 400
    assert db.session.get(Appointment, as_doctor["future"].id).status == (
        Appointment.STATUS_PENDING_PAYMENT
    )


def test_a_cancelled_appointment_has_no_outcome(client, as_doctor):
    as_doctor["past"].status = Appointment.STATUS_CANCELLED
    db.session.commit()

    response = client.post(
        f"/api/doctor/appointments/{as_doctor['past'].id}/outcome",
        json={"status": Appointment.STATUS_NO_SHOW},
    )
    assert response.status_code == 400


def test_an_arbitrary_status_is_refused(client, as_doctor):
    """A doctor must not be able to mark an unpaid appointment paid."""
    response = client.post(
        f"/api/doctor/appointments/{as_doctor['past'].id}/outcome",
        json={"status": "confirmed"},
    )
    assert response.status_code == 400


def test_an_outcome_can_be_corrected(client, as_doctor):
    url = f"/api/doctor/appointments/{as_doctor['past'].id}/outcome"
    client.post(url, json={"status": Appointment.STATUS_NO_SHOW})
    response = client.post(url, json={"status": Appointment.STATUS_COMPLETED})
    assert response.status_code == 200
    assert response.get_json()["status"] == Appointment.STATUS_COMPLETED


# ----------------------------------------------------------- availability


def test_availability_replaces_rather_than_appends(client, as_doctor):
    client.put(
        "/api/doctor/availability",
        json={"availability": [{"day_of_week": 4, "start_time": "10:00", "end_time": "13:00"}]},
    )
    rows = client.get("/api/doctor/availability").get_json()
    assert len(rows) == 1
    assert rows[0]["day_of_week"] == 4


def test_a_window_that_ends_before_it_starts_is_refused(client, as_doctor):
    response = client.put(
        "/api/doctor/availability",
        json={"availability": [{"day_of_week": 1, "start_time": "17:00", "end_time": "09:00"}]},
    )
    assert response.status_code == 400
    assert "availability.0" in response.get_json()["fields"]


def test_slot_length_is_per_window(client, as_doctor):
    """A doctor runs 20-minute follow-ups and 45-minute first visits."""
    client.put(
        "/api/doctor/availability",
        json={
            "availability": [
                {
                    "day_of_week": 1,
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "slot_minutes": 20,
                },
                {
                    "day_of_week": 3,
                    "start_time": "15:00",
                    "end_time": "18:00",
                    "slot_minutes": 45,
                },
            ]
        },
    )
    rows = {
        row["day_of_week"]: row["slot_minutes"]
        for row in client.get("/api/doctor/availability").get_json()
    }
    assert rows == {1: 20, 3: 45}


def test_an_absurd_slot_length_is_refused(client, as_doctor):
    response = client.put(
        "/api/doctor/availability",
        json={
            "availability": [
                {
                    "day_of_week": 1,
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "slot_minutes": 600,
                }
            ]
        },
    )
    assert response.status_code == 400


def test_removing_a_window_leaves_existing_bookings_alone(client, as_doctor):
    """Deleting the appointments here would be far worse than leaving them."""
    client.put("/api/doctor/availability", json={"availability": []})
    assert db.session.get(Appointment, as_doctor["future"].id) is not None
