import pytest

from app.extensions import db
from app.models.doctor import Doctor, DoctorAvailability, Specialty


@pytest.fixture
def directory(app):
    cardio = Specialty.get_or_create("Cardiologist")
    derm = Specialty.get_or_create("Dermatologist")
    db.session.flush()

    approved = Doctor(
        name="Dr. Anwar Hossain",
        specialty=cardio,
        hospital="Padma Heart Centre",
        location="Laxmipur, Rajshahi",
        phone="+8801711000101",
        fee=1500,
        rating=4.8,
        review_count=132,
        experience_years=14,
        approval_status=Doctor.STATUS_APPROVED,
    )
    cheaper = Doctor(
        name="Dr. Farhana Islam",
        specialty=derm,
        hospital="Padma General Hospital",
        location="Kazla, Rajshahi",
        phone="+8801711000104",
        fee=900,
        rating=4.4,
        review_count=61,
        experience_years=6,
        approval_status=Doctor.STATUS_APPROVED,
    )
    pending = Doctor(
        name="Dr. Not Yet Approved",
        specialty=cardio,
        hospital="Barind Specialised Clinic",
        location="Shaheb Bazar, Rajshahi",
        phone="+8801711000199",
        fee=1000,
        approval_status=Doctor.STATUS_PENDING,
    )
    db.session.add_all([approved, cheaper, pending])
    db.session.flush()
    db.session.add(
        DoctorAvailability(
            doctor_id=approved.id, day_of_week=0, start_time="09:00", end_time="13:00"
        )
    )
    db.session.commit()
    return {"approved": approved, "cheaper": cheaper, "pending": pending}


def test_specialty_slug_is_generated(app):
    specialty = Specialty.get_or_create("ENT Specialist")
    db.session.commit()
    assert specialty.slug == "ent-specialist"


def test_get_or_create_does_not_duplicate(app):
    first = Specialty.get_or_create("Cardiologist")
    db.session.commit()
    second = Specialty.get_or_create("cardiologist")
    db.session.commit()
    assert first.id == second.id
    assert Specialty.query.count() == 1


def test_list_returns_only_approved_doctors(client, directory):
    body = client.get("/api/doctors").get_json()
    names = [item["name"] for item in body["items"]]
    assert "Dr. Anwar Hossain" in names
    assert "Dr. Not Yet Approved" not in names
    assert body["total"] == 2


def test_filter_by_specialty_slug(client, directory):
    body = client.get("/api/doctors?specialty=dermatologist").get_json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Dr. Farhana Islam"


def test_search_matches_hospital_and_location(client, directory):
    assert client.get("/api/doctors?q=Kazla").get_json()["total"] == 1
    assert client.get("/api/doctors?q=Padma").get_json()["total"] == 2
    assert client.get("/api/doctors?q=nothing-here").get_json()["total"] == 0


def test_sort_by_fee_ascending(client, directory):
    items = client.get("/api/doctors?sort=fee_low").get_json()["items"]
    assert [item["fee"] for item in items] == [900.0, 1500.0]


def test_pagination_reports_pages(client, directory):
    body = client.get("/api/doctors?per_page=1").get_json()
    assert len(body["items"]) == 1
    assert body["pages"] == 2
    assert body["has_next"] is True


def test_per_page_is_capped(client, directory):
    assert client.get("/api/doctors?per_page=9999").get_json()["per_page"] == 48


def test_detail_includes_availability(client, directory):
    body = client.get(f"/api/doctors/{directory['approved'].id}").get_json()
    assert body["specialty"]["slug"] == "cardiologist"
    assert body["availability"][0]["day_name"] == "Monday"
    assert body["initials"] == "AH"


def test_pending_doctor_detail_is_not_found(client, directory):
    assert client.get(f"/api/doctors/{directory['pending'].id}").status_code == 404


def test_specialties_only_counts_approved(client, directory):
    body = client.get("/api/specialties").get_json()
    counts = {item["slug"]: item["doctor_count"] for item in body}
    assert counts == {"cardiologist": 1, "dermatologist": 1}


def test_listing_does_not_write_to_the_database(client, directory):
    before = DoctorAvailability.query.count()
    client.get("/api/doctors")
    client.get(f"/api/doctors/{directory['approved'].id}")
    assert DoctorAvailability.query.count() == before
