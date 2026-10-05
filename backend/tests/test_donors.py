from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.donor import BloodDonor, DonorRequest


@pytest.fixture
def donor_registry(app):
    today = date.today()

    d1 = BloodDonor(
        name="Md. Rafiqul Islam",
        blood_group="O+",
        area="Laxmipur, Rajshahi",
        hospital_near="Rajshahi Medical College Hospital",
        phone="+8801712000001",
        last_donation_date=today - timedelta(days=120),
        donations_count=7,
        is_available=True,
    )
    d2 = BloodDonor(
        name="Sabbir Hossain",
        blood_group="A+",
        area="Kazla, Rajshahi",
        hospital_near="RUET Medical Centre area",
        phone="+8801712000002",
        last_donation_date=today - timedelta(days=30),  # eligible in 60 days
        donations_count=4,
        is_available=True,
    )
    d3 = BloodDonor(
        name="Tahmid Rahman",
        blood_group="B+",
        area="Talaimari, Rajshahi",
        hospital_near="Barind Specialised Clinic",
        phone="+8801712000003",
        last_donation_date=None,  # First time donor
        donations_count=0,
        is_available=True,
    )
    d4 = BloodDonor(
        name="Imtiaz Shafi",
        blood_group="AB+",
        area="Binodpur, Rajshahi",
        hospital_near="Kazla Family Health",
        phone="+8801712000004",
        last_donation_date=today - timedelta(days=200),
        donations_count=3,
        is_available=False,  # Unavailable
    )

    db.session.add_all([d1, d2, d3, d4])
    db.session.commit()
    return {"d1": d1, "d2": d2, "d3": d3, "d4": d4}


def test_donor_status_calculations(app, donor_registry):
    d1 = donor_registry["d1"]
    assert d1.status == "available"
    assert d1.status_label == "Available Now"
    assert d1.badge_class == "badge-ok"
    assert d1.days_ago == 120

    d2 = donor_registry["d2"]
    assert d2.status == "eligible_soon"
    assert "Eligible in 60 days" in d2.status_label
    assert d2.badge_class == "badge-warn"

    d3 = donor_registry["d3"]
    assert d3.status == "available"
    assert d3.status_label == "Available (New)"
    assert d3.last_donation_formatted == "First-time donor"

    d4 = donor_registry["d4"]
    assert d4.status == "unavailable"
    assert d4.status_label == "Unavailable"
    assert d4.badge_class == "badge-muted"


def test_donor_privacy_guarantee(client, donor_registry):
    # Public list endpoint
    response = client.get("/api/donors")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["items"]) == 4

    for item in data["items"]:
        # CRITICAL PRIVACY REQUIREMENT: Name and phone must never be exposed publicly
        assert "name" not in item
        assert "phone" not in item
        assert "blood_group" in item
        assert "area" in item
        assert "display_id" in item

    # Single donor detail endpoint
    d1_id = donor_registry["d1"].id
    res_single = client.get(f"/api/donors/{d1_id}")
    assert res_single.status_code == 200
    single_data = res_single.get_json()
    assert "name" not in single_data
    assert "phone" not in single_data


def test_list_donors_filters(client, donor_registry):
    # Filter by blood group
    res_group = client.get("/api/donors?blood_group=A%2B")
    assert res_group.status_code == 200
    items = res_group.get_json()["items"]
    assert len(items) == 1
    assert items[0]["blood_group"] == "A+"

    # Filter by status: available
    res_avail = client.get("/api/donors?status=available")
    assert res_avail.status_code == 200
    avail_items = res_avail.get_json()["items"]
    # d1 and d3 are available
    assert len(avail_items) == 2
    for item in avail_items:
        assert item["status"] == "available"

    # Filter by status: eligible_soon
    res_soon = client.get("/api/donors?status=eligible_soon")
    assert res_soon.status_code == 200
    soon_items = res_soon.get_json()["items"]
    assert len(soon_items) == 1
    assert soon_items[0]["status"] == "eligible_soon"

    # Search keyword
    res_search = client.get("/api/donors?q=Kazla")
    assert res_search.status_code == 200
    search_items = res_search.get_json()["items"]
    # d2 is Kazla area, d4 is near Kazla Family Health
    assert len(search_items) == 2


def test_get_single_donor_not_found(client):
    res = client.get("/api/donors/99999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Donor not found"


def test_register_donor_success(client):
    payload = {
        "name": "Istiak Ahmed",
        "blood_group": "B+",
        "area": "Kazla, Rajshahi",
        "hospital_near": "RUET Gate",
        "phone": "+8801700112233",
        "last_donation_date": "2026-01-15",
        "is_available": True,
    }
    res = client.post("/api/donors", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "donor" in data
    assert data["donor"]["blood_group"] == "B+"
    assert data["donor"]["area"] == "Kazla, Rajshahi"
    # Verify privacy on returned donor object
    assert "phone" not in data["donor"]
    assert "name" not in data["donor"]

    # Verify donor is in DB
    db_donor = BloodDonor.query.filter_by(phone="+8801700112233").first()
    assert db_donor is not None
    assert db_donor.name == "Istiak Ahmed"


def test_register_donor_validation_errors(client):
    # Missing required fields
    res = client.post("/api/donors", json={})
    assert res.status_code == 400
    fields = res.get_json()["fields"]
    assert "name" in fields
    assert "blood_group" in fields
    assert "area" in fields
    assert "phone" in fields

    # Invalid blood group
    res_invalid_grp = client.post(
        "/api/donors",
        json={
            "name": "Test User",
            "blood_group": "XYZ",
            "area": "Kazla",
            "phone": "+8801711223344",
        },
    )
    assert res_invalid_grp.status_code == 400
    assert "blood_group" in res_invalid_grp.get_json()["fields"]

    # Future last donation date
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res_future = client.post(
        "/api/donors",
        json={
            "name": "Test User",
            "blood_group": "O+",
            "area": "Kazla",
            "phone": "+8801711223344",
            "last_donation_date": tomorrow,
        },
    )
    assert res_future.status_code == 400
    assert "last_donation_date" in res_future.get_json()["fields"]


def test_donor_contact_request_success(client, donor_registry):
    d1 = donor_registry["d1"]
    payload = {
        "patient_name": "Md. Hasan",
        "hospital": "RMCH Ward 12",
        "units": 2,
        "urgency": "emergency",
        "requester_phone": "+8801799887766",
        "notes": "Emergency bypass surgery scheduled.",
    }
    res = client.post(f"/api/donors/{d1.id}/requests", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "request" in data
    assert data["request"]["patient_name"] == "Md. Hasan"
    assert data["request"]["units"] == 2
    assert data["request"]["urgency"] == "emergency"

    req_in_db = DonorRequest.query.filter_by(donor_id=d1.id).first()
    assert req_in_db is not None
    assert req_in_db.patient_name == "Md. Hasan"
    assert req_in_db.hospital == "RMCH Ward 12"


def test_donor_contact_request_validation(client, donor_registry):
    d1 = donor_registry["d1"]
    res = client.post(f"/api/donors/{d1.id}/requests", json={})
    assert res.status_code == 400
    fields = res.get_json()["fields"]
    assert "patient_name" in fields
    assert "hospital" in fields
    assert "requester_phone" in fields


def test_donor_contact_request_nonexistent_donor(client):
    res = client.post(
        "/api/donors/99999/requests",
        json={
            "patient_name": "Md. Hasan",
            "hospital": "RMCH",
            "units": 1,
            "urgency": "emergency",
            "requester_phone": "+8801799887766",
        },
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "Donor not found"


def test_donor_stats_and_compatibility(client, donor_registry):
    res_stats = client.get("/api/donors/stats")
    assert res_stats.status_code == 200
    stats = res_stats.get_json()
    assert stats["total_donors"] == 4
    assert stats["available_donors"] == 2
    assert "O+" in stats["by_group"]

    res_compat = client.get("/api/donors/compatibility")
    assert res_compat.status_code == 200
    compat = res_compat.get_json()
    assert "O-" in compat
    assert "AB+" in compat
