"""Assistant endpoints, with the language model replaced.

CI has no API key and must never make a network call, so every test here
patches `llm.complete`. That also lets us assert how the flow behaves when the
model misbehaves or is unavailable.
"""

import json

import pytest

from app.extensions import db
from app.models.chat import ChatSession
from app.models.user import User


@pytest.fixture
def patient(app):
    user = User(email="patient@caresphere.test", name="Test Patient")
    user.set_password("a-good-password")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def signed_in(client, patient):
    client.post("/api/login", json={"email": patient.email, "password": "a-good-password"})
    return client


@pytest.fixture
def fake_llm(monkeypatch):
    """Queue replies; each call to the model pops the next one."""
    replies: list[str | None] = []

    def fake_complete(messages, temperature=0.2, max_tokens=700):
        return replies.pop(0) if replies else None

    monkeypatch.setattr("app.services.llm.complete", fake_complete)
    return replies


def reasoner(**overrides) -> str:
    payload = {
        "possible_conditions": [{"name": "Tension headache", "likelihood": "medium"}],
        "red_flags": [],
        "follow_up_questions": ["Does light make it worse?"],
        "likely_specialty": "Neurologist",
        "urgency": "low",
        "assessment_complete": False,
        "summary": "Likely benign but worth review.",
    }
    payload.update(overrides)
    return json.dumps(payload)


NORMALISED = json.dumps(
    {"normalized_text": "headache for two days", "symptoms": ["headache"], "duration": "2 days"}
)


def start(client) -> str:
    response = client.post("/api/chat/sessions")
    assert response.status_code == 201
    return response.get_json()["id"]


# ------------------------------------------------------------------- access


def test_anonymous_cannot_start_an_assessment(client):
    assert client.post("/api/chat/sessions").status_code == 401


def test_sessions_are_private_to_their_owner(client, signed_in, app):
    public_id = start(signed_in)
    signed_in.post("/api/logout")

    other = User(email="other@caresphere.test", name="Other")
    other.set_password("a-good-password")
    db.session.add(other)
    db.session.commit()
    signed_in.post("/api/login", json={"email": other.email, "password": "a-good-password"})

    assert signed_in.get(f"/api/chat/sessions/{public_id}").status_code == 404


# --------------------------------------------------------------------- flow


def test_starting_a_session_returns_a_greeting(signed_in):
    body = signed_in.post("/api/chat/sessions").get_json()
    assert body["step"] == "collecting_symptoms"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["sender"] == "bot"


def test_first_message_asks_a_follow_up(signed_in, fake_llm):
    fake_llm.extend([NORMALISED, reasoner()])
    public_id = start(signed_in)

    body = signed_in.post(
        f"/api/chat/sessions/{public_id}/messages", json={"message": "my head hurts"}
    ).get_json()

    assert body["message"]["kind"] == "question"
    assert body["message"]["data"]["question"] == "Does light make it worse?"
    assert body["session"]["step"] == "questioning"


def test_assessment_completes_with_a_specialty_and_slug(signed_in, fake_llm):
    """A rash is not an ambiguous presentation, so two questions is the floor."""
    rash = json.dumps({"normalized_text": "itchy red rash on my arm"})
    fake_llm.extend(
        [
            rash,
            reasoner(likely_specialty="Dermatologist"),
            reasoner(likely_specialty="Dermatologist", assessment_complete=True),
            reasoner(
                likely_specialty="Dermatologist",
                assessment_complete=True,
                follow_up_questions=[],
            ),
        ]
    )
    public_id = start(signed_in)
    for reply in ("itchy red rash on my arm", "about three days", "no fever"):
        body = signed_in.post(
            f"/api/chat/sessions/{public_id}/messages", json={"message": reply}
        ).get_json()

    assert body["message"]["kind"] == "recommendation"
    data = body["message"]["data"]
    assert data["specialty"] == "Dermatologist"
    assert data["specialty_slug"] == "dermatologist"
    assert data["disclaimer"]
    assert data["next_steps"]
    assert body["session"]["is_complete"] is True


def test_emergency_short_circuits_the_model(signed_in, fake_llm):
    """No model reply is queued - the rules alone must escalate."""
    fake_llm.append(NORMALISED)
    public_id = start(signed_in)

    body = signed_in.post(
        f"/api/chat/sessions/{public_id}/messages",
        json={"message": "crushing chest pain going into my left arm"},
    ).get_json()

    assert body["message"]["kind"] == "emergency"
    assert body["session"]["urgency"] == "emergency"
    assert body["message"]["data"]["actions"]


def test_chest_pain_is_not_concluded_after_one_answer(signed_in, fake_llm):
    """Regression guard for the prototype's early-completion bug."""
    fake_llm.extend(
        [
            json.dumps({"normalized_text": "chest pain after eating"}),
            reasoner(assessment_complete=True, likely_specialty="Gastroenterologist"),
        ]
    )
    public_id = start(signed_in)
    body = signed_in.post(
        f"/api/chat/sessions/{public_id}/messages", json={"message": "chest pain after eating"}
    ).get_json()

    assert body["message"]["kind"] == "question"


def test_model_outage_degrades_instead_of_failing(signed_in, fake_llm):
    """No replies queued at all: every call returns None."""
    public_id = start(signed_in)
    response = signed_in.post(
        f"/api/chat/sessions/{public_id}/messages", json={"message": "itchy rash on my arm"}
    )

    assert response.status_code == 200
    assert response.get_json()["message"]["data"]["degraded"] is True


def test_completed_session_rejects_further_messages(signed_in, fake_llm, app):
    public_id = start(signed_in)
    session = ChatSession.query.filter_by(public_id=public_id).one()
    session.current_step = ChatSession.STEP_COMPLETE
    db.session.commit()

    response = signed_in.post(f"/api/chat/sessions/{public_id}/messages", json={"message": "hello"})
    assert response.status_code == 409


# --------------------------------------------------------------- validation


def test_empty_message_is_rejected(signed_in):
    public_id = start(signed_in)
    response = signed_in.post(f"/api/chat/sessions/{public_id}/messages", json={"message": "   "})
    assert response.status_code == 400


def test_overlong_message_is_rejected(signed_in):
    public_id = start(signed_in)
    response = signed_in.post(
        f"/api/chat/sessions/{public_id}/messages", json={"message": "x" * 1001}
    )
    assert response.status_code == 400


def test_unknown_session_returns_404(signed_in):
    assert (
        signed_in.post(
            "/api/chat/sessions/does-not-exist/messages", json={"message": "hi"}
        ).status_code
        == 404
    )


# ----------------------------------------------------------------- history


def test_history_lists_and_deletes(signed_in, fake_llm):
    public_id = start(signed_in)
    assert len(signed_in.get("/api/chat/sessions").get_json()) == 1

    assert signed_in.delete(f"/api/chat/sessions/{public_id}").status_code == 200
    assert signed_in.get("/api/chat/sessions").get_json() == []


def test_transcript_is_returned_in_order(signed_in, fake_llm):
    fake_llm.extend([NORMALISED, reasoner()])
    public_id = start(signed_in)
    signed_in.post(f"/api/chat/sessions/{public_id}/messages", json={"message": "my head hurts"})

    messages = signed_in.get(f"/api/chat/sessions/{public_id}").get_json()["messages"]
    assert [m["sender"] for m in messages] == ["bot", "user", "bot"]
