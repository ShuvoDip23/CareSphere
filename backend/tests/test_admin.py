"""Admin console: access control and doctor CRUD."""

import pytest

from app.extensions import db
from app.models.doctor import Doctor, DoctorAvailability, Specialty
from app.models.user import User

NEW_DOCTOR = {
    "name": "Dr. Nazmul Karim",
    "specialty": "Cardiologist",
    "hospital": "Padma Heart Centre",
    "location": "Laxmipur, Rajshahi",
    "phone": "+8801711000200",
    "fee": 1400,
    "experience_years": 11,
    "qualification": "MBBS, MD (Cardiology)",
}


def _make_user(email, role, password="a-good-password"):
    user = User(email=email, name=email.split("@")[0], role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _sign_in(client, email, password="a-good-password"):
    return client.post("/api/login", json={"email": email, "password": password})


@pytest.fixture
def admin(app):
    return _make_user("admin@caresphere.test", User.ROLE_ADMIN)


@pytest.fixture
def admin_client(client, admin):
    _sign_in(client, admin.email)
    return client


@pytest.fixture
def existing(app):
    specialty = Specialty.get_or_create("Dermatologist")
    db.session.flush()
    doctor = Doctor(
        name="Dr. Farhana Islam",
        specialty=specialty,
        hospital="Padma General Hospital",
        location="Kazla, Rajshahi",
        phone="+8801711000104",
        fee=900,
        experience_years=6,
        approval_status=Doctor.STATUS_APPROVED,
    )
    db.session.add(doctor)
    db.session.flush()
    db.session.add(
        DoctorAvailability(doctor_id=doctor.id, day_of_week=1, start_time="10:00", end_time="14:00")
    )
    db.session.commit()
    return doctor


# ------------------------------------------------------------------ access


def test_anonymous_is_rejected(client):
    assert client.get("/api/admin/doctors").status_code == 401


def test_patient_is_forbidden(client, app):
    _make_user("patient@caresphere.test", User.ROLE_PATIENT)
    _sign_in(client, "patient@caresphere.test")
    assert client.get("/api/admin/doctors").status_code == 403


def test_doctor_role_is_forbidden(client, app):
    _make_user("doc@caresphere.test", User.ROLE_DOCTOR)
    _sign_in(client, "doc@caresphere.test")
    assert client.post("/api/admin/doctors", json=NEW_DOCTOR).status_code == 403


def test_role_change_takes_effect_without_re_login(client, app):
    """The prototype cached the role in the session, so a demotion did nothing."""
    user = _make_user("temp@caresphere.test", User.ROLE_ADMIN)
    _sign_in(client, user.email)
    assert client.get("/api/admin/doctors").status_code == 200

    user.role = User.ROLE_PATIENT
    db.session.commit()
    assert client.get("/api/admin/doctors").status_code == 403


# ------------------------------------------------------------------- CRUD


def test_create_doctor_and_specialty(admin_client):
    response = admin_client.post("/api/admin/doctors", json=NEW_DOCTOR)
    assert response.status_code == 201
    body = response.get_json()
    assert body["specialty"]["slug"] == "cardiologist"
    assert body["approval_status"] == "approved"
    assert Specialty.query.filter_by(slug="cardiologist").count() == 1


def test_create_reuses_existing_specialty(admin_client, existing):
    admin_client.post("/api/admin/doctors", json={**NEW_DOCTOR, "specialty": "dermatologist"})
    assert Specialty.query.filter_by(slug="dermatologist").count() == 1


def test_create_with_availability(admin_client):
    response = admin_client.post(
        "/api/admin/doctors",
        json={
            **NEW_DOCTOR,
            "availability": [
                {"day_of_week": 0, "start_time": "09:00", "end_time": "13:00"},
                {"day_of_week": 3, "start_time": "16:00", "end_time": "20:00"},
            ],
        },
    )
    assert len(response.get_json()["availability"]) == 2


def test_create_rejects_missing_fields(admin_client):
    response = admin_client.post("/api/admin/doctors", json={"name": "Dr. Nobody"})
    assert response.status_code == 400
    assert "hospital" in response.get_json()["fields"]


def test_create_rejects_bad_fee(admin_client):
    response = admin_client.post("/api/admin/doctors", json={**NEW_DOCTOR, "fee": "free"})
    assert response.status_code == 400
    assert "fee" in response.get_json()["fields"]


def test_update_is_partial(admin_client, existing):
    response = admin_client.put(f"/api/admin/doctors/{existing.id}", json={"fee": 1250})
    assert response.status_code == 200
    body = response.get_json()
    assert body["fee"] == 1250.0
    assert body["name"] == "Dr. Farhana Islam"


def test_update_replaces_availability(admin_client, existing):
    admin_client.put(
        f"/api/admin/doctors/{existing.id}",
        json={"availability": [{"day_of_week": 5, "start_time": "08:00", "end_time": "11:00"}]},
    )
    rows = DoctorAvailability.query.filter_by(doctor_id=existing.id).all()
    assert len(rows) == 1
    assert rows[0].day_of_week == 5


def test_availability_rejects_reversed_window(admin_client, existing):
    response = admin_client.put(
        f"/api/admin/doctors/{existing.id}",
        json={"availability": [{"day_of_week": 2, "start_time": "18:00", "end_time": "09:00"}]},
    )
    assert response.status_code == 400


def test_status_change_hides_doctor_from_public_listing(admin_client, existing):
    assert admin_client.get("/api/doctors").get_json()["total"] == 1

    admin_client.post(
        f"/api/admin/doctors/{existing.id}/status",
        json={"approval_status": "rejected", "rejection_note": "Could not verify registration."},
    )
    assert admin_client.get("/api/doctors").get_json()["total"] == 0

    detail = admin_client.get(f"/api/admin/doctors/{existing.id}").get_json()
    assert detail["rejection_note"] == "Could not verify registration."


def test_approving_clears_the_rejection_note(admin_client, existing):
    admin_client.post(
        f"/api/admin/doctors/{existing.id}/status",
        json={"approval_status": "rejected", "rejection_note": "Missing documents."},
    )
    body = admin_client.post(
        f"/api/admin/doctors/{existing.id}/status", json={"approval_status": "approved"}
    ).get_json()
    assert body["rejection_note"] is None


def test_delete_removes_doctor_and_availability(admin_client, existing):
    doctor_id = existing.id
    assert admin_client.delete(f"/api/admin/doctors/{doctor_id}").status_code == 200
    assert db.session.get(Doctor, doctor_id) is None
    assert DoctorAvailability.query.filter_by(doctor_id=doctor_id).count() == 0


def test_admin_list_includes_every_status(admin_client, existing):
    admin_client.post("/api/admin/doctors", json={**NEW_DOCTOR, "approval_status": "pending"})
    assert len(admin_client.get("/api/admin/doctors").get_json()) == 2
    assert len(admin_client.get("/api/admin/doctors?status=pending").get_json()) == 1


def test_stats_counts_by_status(admin_client, existing):
    admin_client.post("/api/admin/doctors", json={**NEW_DOCTOR, "approval_status": "pending"})
    stats = admin_client.get("/api/admin/stats").get_json()
    assert stats["total"] == 2
    assert stats["approved"] == 1
    assert stats["pending"] == 1


def test_missing_doctor_returns_404(admin_client):
    assert admin_client.get("/api/admin/doctors/9999").status_code == 404
    assert admin_client.delete("/api/admin/doctors/9999").status_code == 404
