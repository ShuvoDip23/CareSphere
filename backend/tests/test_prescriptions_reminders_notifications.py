from datetime import date, datetime

from app.extensions import db
from app.models.notification import Notification


def login(client):
    return client.post("/api/login", json={"email": "patient@example.com", "password": "correct-horse"})


def test_prescription_requires_patient_verification_and_is_private(client, patient):
    login(client)
    response = client.post("/api/prescriptions", json={"raw_text": "Rx", "items": []})
    assert response.status_code == 400
    response = client.post("/api/prescriptions", json={"raw_text": "Rx",
        "items": [{"medicine_name": "Example", "dosage": "1 tablet", "frequency": "daily"}]})
    assert response.status_code == 201
    assert response.json["prescription"]["verified"] is True
    client.post("/api/logout")
    other = client.post("/api/register", json={"name":"Other", "email":"other@example.com", "password":"correct-horse"})
    assert other.status_code == 201
    assert client.get("/api/prescriptions").json["prescriptions"] == []


def test_reminder_schedule_and_explicit_taken_log(client, patient):
    login(client)
    response = client.post("/api/reminders", json={"medicine_name":"Example", "dosage":"1 tab",
        "frequency":"daily", "times":["23:59"], "start_date":date.today().isoformat()})
    assert response.status_code == 201
    reminder_id = response.json["reminder"]["id"]
    schedule = client.get("/api/reminders/today").json["schedule"]
    assert schedule and schedule[0]["status"] in ("upcoming", "missed")
    target = datetime.fromisoformat(schedule[0]["scheduled_for"])
    result = client.post(f"/api/reminders/{reminder_id}/log",
        json={"status":"taken", "scheduled_for":target.isoformat()})
    assert result.status_code == 200
    assert result.json["log"]["status"] == "taken"


def test_notification_inbox_is_user_scoped(client, patient):
    db.session.add(Notification(patient_id=patient.id, kind="system", title="Hello", message="World"))
    db.session.commit()
    login(client)
    response = client.get("/api/notifications")
    assert response.status_code == 200
    assert response.json["unread_count"] == 1
    nid = response.json["notifications"][0]["id"]
    assert client.patch(f"/api/notifications/{nid}/read").status_code == 200
    assert client.get("/api/notifications").json["unread_count"] == 0
