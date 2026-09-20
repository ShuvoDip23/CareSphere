import hashlib

from app.models.user import User


def test_register_creates_patient_and_starts_session(client):
    response = client.post(
        "/api/register",
        json={"name": "Shuvo", "email": "Shuvo@Example.com", "password": "a-good-password"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["role"] == "patient"
    assert body["user"]["email"] == "shuvo@example.com"

    assert client.get("/api/me").get_json()["authenticated"] is True


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/register",
        json={"name": "Shuvo", "email": "a@b.com", "password": "short"},
    )
    assert response.status_code == 400


def test_role_cannot_be_set_from_request_body(client):
    client.post(
        "/api/register",
        json={
            "name": "Attacker",
            "email": "attacker@example.com",
            "password": "a-good-password",
            "role": "admin",
        },
    )
    user = User.query.filter_by(email="attacker@example.com").first()
    assert user.role == "patient"


def test_password_is_not_stored_as_bare_sha256(patient):
    """Regression guard against the previous unsalted hashing scheme."""
    legacy = hashlib.sha256(b"correct-horse").hexdigest()
    assert patient.password_hash != legacy
    assert patient.password_hash != "correct-horse"
    assert patient.check_password("correct-horse")
    assert not patient.check_password("wrong-password")


def test_login_rejects_bad_credentials_without_leaking_existence(client, patient):
    unknown = client.post("/api/login", json={"email": "nobody@example.com", "password": "x"})
    wrong = client.post("/api/login", json={"email": "patient@example.com", "password": "wrong"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.get_json()["error"] == wrong.get_json()["error"]


def test_logout_clears_session(client, patient):
    client.post("/api/login", json={"email": "patient@example.com", "password": "correct-horse"})
    assert client.get("/api/me").get_json()["authenticated"] is True
    client.post("/api/logout")
    assert client.get("/api/me").get_json()["authenticated"] is False
