"""Doctor sign-up, the approval queue, and which edits re-open a review."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.doctor import Doctor, Specialty
from app.models.user import User

APPLICATION = {
    "email": "newdoctor@example.com",
    "password": "correct-horse",
    "name": "Dr. Sabina Yasmin",
    "specialty": "Paediatrician",
    "qualification": "MBBS, FCPS (Paediatrics)",
    "hospital": "Barind Specialised Clinic",
    "location": "Shaheb Bazar, Rajshahi",
    "phone": "+8801711000155",
    "fee": 1200,
    "experience_years": 9,
}


def _apply(client, **overrides):
    return client.post("/api/register/doctor", json={**APPLICATION, **overrides})


@pytest.fixture
def admin(app):
    user = User(email="admin@example.com", name="Admin", role=User.ROLE_ADMIN)
    user.set_password("correct-horse")
    db.session.add(user)
    db.session.commit()
    return user


# ------------------------------------------------------------ applying


def test_an_application_creates_account_profile_and_link(client, app):
    response = _apply(client)
    assert response.status_code == 201

    body = response.get_json()
    assert body["user"]["role"] == User.ROLE_DOCTOR
    assert body["doctor"]["approval_status"] == Doctor.STATUS_PENDING

    doctor = Doctor.query.one()
    user = User.query.filter_by(email=APPLICATION["email"]).one()
    assert doctor.user_id == user.id


def test_an_applicant_cannot_approve_themselves(client, app):
    """Same stance /api/register already takes on `role`."""
    response = _apply(client, approval_status="approved", rejection_note="n/a")
    assert response.status_code == 201
    assert Doctor.query.one().approval_status == Doctor.STATUS_PENDING


def test_a_pending_doctor_is_invisible_to_patients(client, app):
    _apply(client)
    doctor_id = Doctor.query.one().id

    assert client.get("/api/doctors").get_json()["items"] == []
    # 404 rather than 403, so pending applications cannot be enumerated.
    assert client.get(f"/api/doctors/{doctor_id}").status_code == 404


def test_a_pending_doctor_cannot_be_booked(client, app, patient):
    _apply(client)
    doctor_id = Doctor.query.one().id

    client.post("/api/logout")
    client.post("/api/login", json={"email": patient.email, "password": "correct-horse"})
    response = client.post(
        "/api/appointments",
        json={"doctor_id": doctor_id, "date": "2027-01-04", "time": "09:00", "reason": "Checkup"},
    )
    assert response.status_code == 404


def test_every_problem_is_reported_at_once(client, app):
    """Fixing the password then discovering the fee is wrong is a bad flow."""
    response = _apply(client, password="short", fee="not-a-number", hospital="")
    assert response.status_code == 400

    fields = response.get_json()["fields"]
    assert {"password", "fee", "hospital"} <= set(fields)


def test_a_duplicate_email_is_refused(client, app, patient):
    response = _apply(client, email=patient.email)
    assert response.status_code == 400
    assert "email" in response.get_json()["fields"]
    assert Doctor.query.count() == 0


def test_a_failed_application_leaves_nothing_behind(client, app):
    """An account with no profile is worse than no application at all."""
    _apply(client, fee="not-a-number")
    assert User.query.filter_by(email=APPLICATION["email"]).count() == 0
    assert Doctor.query.count() == 0


def test_the_database_rejects_two_profiles_on_one_account(client, app):
    """Links are now created by concurrent web requests, not one CLI run."""
    _apply(client)
    user = User.query.filter_by(email=APPLICATION["email"]).one()

    db.session.add(
        Doctor(
            name="Dr. Second Profile",
            specialty=Specialty.get_or_create("Cardiologist"),
            hospital="Elsewhere",
            location="Rajshahi",
            phone="+8801711000166",
            fee=900,
            user_id=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_consulting_hours_can_be_submitted_with_the_application(client, app):
    response = _apply(
        client,
        availability=[{"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"}],
    )
    assert response.status_code == 201
    assert len(response.get_json()["doctor"]["availability"]) == 1


# ------------------------------------------------------------- approval


def test_approval_publishes_the_doctor(client, app, admin):
    _apply(client)
    doctor_id = Doctor.query.one().id

    client.post("/api/logout")
    client.post("/api/login", json={"email": admin.email, "password": "correct-horse"})
    assert (
        client.post(
            f"/api/admin/doctors/{doctor_id}/status", json={"approval_status": "approved"}
        ).status_code
        == 200
    )

    client.post("/api/logout")
    assert len(client.get("/api/doctors").get_json()["items"]) == 1


def test_rejection_keeps_the_note_for_the_doctor_to_read(client, app, admin):
    _apply(client)
    doctor_id = Doctor.query.one().id

    client.post("/api/logout")
    client.post("/api/login", json={"email": admin.email, "password": "correct-horse"})
    client.post(
        f"/api/admin/doctors/{doctor_id}/status",
        json={"approval_status": "rejected", "rejection_note": "Attach your BMDC number."},
    )

    client.post("/api/logout")
    client.post("/api/login", json={"email": APPLICATION["email"], "password": "correct-horse"})
    body = client.get("/api/doctor/me").get_json()
    assert body["approval_status"] == Doctor.STATUS_REJECTED
    assert "BMDC" in body["rejection_note"]


# ----------------------------------------------- which edits re-open review


@pytest.fixture
def approved(client, app, admin):
    _apply(client)
    doctor = Doctor.query.one()
    doctor.approval_status = Doctor.STATUS_APPROVED
    db.session.commit()

    client.post("/api/logout")
    client.post("/api/login", json={"email": APPLICATION["email"], "password": "correct-horse"})
    return doctor


def test_changing_consulting_hours_does_not_need_re_approval(client, approved):
    """A doctor cancelling tomorrow's clinic cannot wait for an admin."""
    response = client.put(
        "/api/doctor/availability",
        json={"availability": [{"day_of_week": 5, "start_time": "10:00", "end_time": "13:00"}]},
    )
    assert response.status_code == 200
    assert Doctor.query.one().approval_status == Doctor.STATUS_APPROVED


def test_changing_phone_bio_or_fee_applies_immediately(client, approved):
    response = client.put(
        "/api/doctor/profile",
        json={"phone": "+8801799000111", "bio": "Now consulting on Fridays.", "fee": 1400},
    )
    assert response.status_code == 200

    doctor = Doctor.query.one()
    assert doctor.approval_status == Doctor.STATUS_APPROVED
    assert doctor.phone == "+8801799000111"
    assert float(doctor.fee) == 1400.0


def test_changing_qualification_sends_the_profile_back_to_the_queue(client, approved):
    """The admin approved a claim; changing it re-opens their question."""
    response = client.put("/api/doctor/profile", json={"qualification": "MBBS, FCPS, PhD"})
    assert response.status_code == 200

    doctor = Doctor.query.one()
    assert doctor.approval_status == Doctor.STATUS_PENDING
    assert "qualification" in doctor.pending_reason


def test_the_reason_names_every_changed_field(client, approved):
    client.put(
        "/api/doctor/profile",
        json={"specialty": "Cardiologist", "hospital": "Padma Heart Centre"},
    )
    reason = Doctor.query.one().pending_reason
    assert "specialty" in reason and "hospital" in reason


def test_resubmitting_the_same_value_does_not_re_open_a_review(client, approved):
    """An editor that posts the whole form must not trigger a review."""
    response = client.put(
        "/api/doctor/profile",
        json={
            "name": APPLICATION["name"],
            "qualification": APPLICATION["qualification"],
            "hospital": APPLICATION["hospital"],
            "bio": "Only the bio actually changed.",
        },
    )
    assert response.status_code == 200
    assert Doctor.query.one().approval_status == Doctor.STATUS_APPROVED


def test_a_profile_back_in_the_queue_leaves_the_directory(client, approved):
    client.put("/api/doctor/profile", json={"hospital": "A Different Hospital"})
    client.post("/api/logout")
    assert client.get("/api/doctors").get_json()["items"] == []


def test_existing_appointments_survive_a_re_review(client, approved, patient, app):
    from datetime import UTC, datetime, timedelta

    from app.models.appointment import Appointment

    when = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=4)
    booking = Appointment(
        user_id=patient.id,
        doctor_id=approved.id,
        scheduled_for=when,
        slot_key=Appointment.build_slot_key(when),
        reason="Already booked before the edit",
        fee_at_booking=approved.fee,
    )
    db.session.add(booking)
    db.session.commit()

    client.put("/api/doctor/profile", json={"hospital": "A Different Hospital"})
    assert db.session.get(Appointment, booking.id) is not None


def test_a_doctor_cannot_approve_themselves_through_the_profile_editor(client, approved):
    response = client.put(
        "/api/doctor/profile",
        json={"qualification": "MBBS, PhD", "approval_status": "approved"},
    )
    assert response.status_code == 200
    assert Doctor.query.one().approval_status == Doctor.STATUS_PENDING


def test_a_rejected_doctor_can_edit_and_resubmit(client, approved):
    """Otherwise the rejection note is advice they cannot act on."""
    doctor = Doctor.query.one()
    doctor.approval_status = Doctor.STATUS_REJECTED
    doctor.rejection_note = "Attach your BMDC number."
    db.session.commit()

    response = client.put("/api/doctor/profile", json={"qualification": "MBBS, BMDC A-12345"})
    assert response.status_code == 200
    assert Doctor.query.one().qualification == "MBBS, BMDC A-12345"
