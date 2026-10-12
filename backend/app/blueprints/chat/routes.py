"""AI health assistant endpoints.

The blueprint orchestrates only: it calls the LLM service, hands the reply to
the triage rules, persists the turn and returns structured data. All decisions
live in `services/triage.py`, all network I/O in `services/llm.py`.
"""

import uuid
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request

from ...extensions import db
from ...models.chat import ChatMessage, ChatSession
from ...services import llm, triage
from ...utils.security import current_user, login_required

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

MAX_MESSAGE_LENGTH = 1000
MAX_TURNS_PER_SESSION = 24
HISTORY_LIMIT = 20

GREETING = (
    "Hello. Describe what you are feeling in your own words - for example "
    "\u201cchest pain after eating\u201d, \u201cI feel short of breath\u201d or "
    "\u201cred itchy rash on my arm\u201d."
)


def _session_or_404(public_id: str, user_id: int) -> ChatSession | None:
    return ChatSession.query.filter_by(public_id=public_id, user_id=user_id).first()


def _add_bot(session: ChatSession, text: str, kind: str, data: dict | None = None) -> ChatMessage:
    message = ChatMessage(session=session, sender=ChatMessage.SENDER_BOT, kind=kind, text=text)
    message.data = data
    db.session.add(message)
    return message


def _recommendation_payload(reasoning: dict) -> dict:
    specialty = reasoning["likely_specialty"]
    return {
        "possible_conditions": reasoning["possible_conditions"],
        "red_flags": reasoning["red_flags"],
        "specialty": specialty,
        "specialty_slug": triage.specialty_slug(specialty),
        "urgency": reasoning["urgency"],
        "summary": reasoning["summary"],
        "next_steps": triage.next_steps_for(specialty, reasoning["urgency"]),
        "degraded": reasoning.get("degraded", False),
        "disclaimer": triage.DISCLAIMER,
    }


def _complete(session: ChatSession, state: dict, reasoning: dict) -> ChatMessage:
    """Close the session with either an emergency alert or a recommendation."""
    if reasoning["urgency"] == "emergency":
        message = _add_bot(
            session,
            "Your symptoms may need immediate medical attention.",
            ChatMessage.KIND_EMERGENCY,
            {
                "reason": reasoning["summary"],
                "actions": list(triage.EMERGENCY_ACTIONS),
                "disclaimer": triage.DISCLAIMER,
            },
        )
    else:
        message = _add_bot(
            session,
            f"Based on what you have described, a {reasoning['likely_specialty']} "
            "is the most appropriate specialist.",
            ChatMessage.KIND_RECOMMENDATION,
            _recommendation_payload(reasoning),
        )

    state["reasoning"] = reasoning
    session.state = state
    session.current_step = ChatSession.STEP_COMPLETE
    session.recommended_specialty = reasoning["likely_specialty"]
    session.urgency = reasoning["urgency"]
    session.ended_at = datetime.now(UTC)
    return message


def _ask(session: ChatSession, state: dict, reasoning: dict) -> ChatMessage:
    question = triage.next_question(state, reasoning)
    state["pending_question"] = question
    state["asked"] = [*state.get("asked", []), question]
    state["question_count"] = state.get("question_count", 0) + 1
    state["reasoning"] = reasoning
    session.state = state
    session.current_step = ChatSession.STEP_QUESTIONING

    return _add_bot(
        session,
        question,
        ChatMessage.KIND_QUESTION,
        {
            "question": question,
            "possible_conditions": reasoning["possible_conditions"],
            "red_flags": reasoning["red_flags"],
            "progress": {
                "asked": state["question_count"],
                "max": triage.MAX_QUESTIONS,
            },
            "degraded": reasoning.get("degraded", False),
        },
    )


# ------------------------------------------------------------------- routes


@chat_bp.post("/sessions")
@login_required
def start_session():
    """Open a new assessment and return the greeting."""
    user = current_user()
    session = ChatSession(user_id=user.id, public_id=str(uuid.uuid4()))
    session.state = {}
    db.session.add(session)
    db.session.flush()

    _add_bot(session, GREETING, ChatMessage.KIND_TEXT, {"disclaimer": triage.DISCLAIMER})
    db.session.commit()

    return jsonify(session.to_dict(include_messages=True)), 201


@chat_bp.post("/sessions/<public_id>/messages")
@login_required
def send_message(public_id: str):
    user = current_user()
    session = _session_or_404(public_id, user.id)
    if session is None:
        return jsonify({"error": "Assessment not found"}), 404
    if session.is_complete:
        return jsonify({"error": "This assessment is already complete. Start a new one."}), 409
    if len(session.messages) >= MAX_TURNS_PER_SESSION:
        return jsonify({"error": "This assessment has run too long. Start a new one."}), 409

    body = request.get_json(silent=True) or {}
    text = " ".join(str(body.get("message") or "").split())
    if not text:
        return jsonify({"error": "Please describe your symptoms"}), 400
    if len(text) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Please keep it under {MAX_MESSAGE_LENGTH} characters"}), 400

    db.session.add(
        ChatMessage(
            session=session, sender=ChatMessage.SENDER_USER, kind=ChatMessage.KIND_TEXT, text=text
        )
    )

    state = session.state

    if session.current_step == ChatSession.STEP_COLLECTING:
        normalised = triage.parse_normaliser(
            llm.complete(triage.build_normaliser_messages(text), temperature=0.1, max_tokens=300),
            text,
        )
        state.update(normalised)
        state["raw_symptoms"] = text
        state.update({"answers": {}, "asked": [], "pending_question": None, "question_count": 0})
    else:
        pending = state.get("pending_question")
        answers = dict(state.get("answers") or {})
        answers[pending or f"answer_{len(answers) + 1}"] = text
        state["answers"] = answers
        state["pending_question"] = None

    # The rules run on every turn, before and regardless of the model.
    verdict = triage.check_emergency(text, state)
    if verdict["is_emergency"]:
        reasoning = triage.emergency_reasoning(verdict["reason"])
    else:
        reasoning = triage.parse_reasoner(
            llm.complete(triage.build_reasoner_messages(state), temperature=0.2, max_tokens=700),
            state,
        )

    if triage.decide_next_step(state, reasoning) == "ask":
        message = _ask(session, state, reasoning)
    else:
        message = _complete(session, state, reasoning)

    db.session.commit()
    return jsonify({"session": session.to_dict(), "message": message.to_dict()}), 200


@chat_bp.get("/sessions")
@login_required
def list_sessions():
    user = current_user()
    sessions = (
        ChatSession.query.filter_by(user_id=user.id)
        .order_by(ChatSession.started_at.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )
    return jsonify([s.to_dict() for s in sessions])


@chat_bp.get("/sessions/<public_id>")
@login_required
def get_session(public_id: str):
    user = current_user()
    session = _session_or_404(public_id, user.id)
    if session is None:
        return jsonify({"error": "Assessment not found"}), 404
    return jsonify(session.to_dict(include_messages=True))


@chat_bp.delete("/sessions/<public_id>")
@login_required
def delete_session(public_id: str):
    user = current_user()
    session = _session_or_404(public_id, user.id)
    if session is None:
        return jsonify({"error": "Assessment not found"}), 404
    db.session.delete(session)
    db.session.commit()
    return jsonify({"message": "Assessment deleted"})
