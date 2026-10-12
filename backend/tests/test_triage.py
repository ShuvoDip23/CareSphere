"""Triage rules. No mocks needed - this module is pure logic."""

import pytest

from app.services import triage

# ------------------------------------------------------------ emergency rules


@pytest.mark.parametrize(
    "text",
    [
        "I can't breathe properly",
        "chest pain going down my left arm",
        "my left arm hurts and I have chest pain",
        "he fainted in the kitchen",
        "her speech is slurred and her face is drooping",
        "I am coughing up blood",
        "sudden vision loss in one eye",
        "my throat is closing up",
    ],
)
def test_single_phrase_escalates(text):
    assert triage.check_emergency(text)["is_emergency"] is True


def test_two_red_flags_escalate_together():
    verdict = triage.check_emergency("I have shortness of breath and a cold sweat")
    assert verdict["is_emergency"] is True
    assert verdict["matched_by"] == "red_flags"


def test_single_red_flag_does_not_escalate():
    assert triage.check_emergency("I have been sweating a lot")["is_emergency"] is False


def test_ordinary_complaint_does_not_escalate():
    assert triage.check_emergency("itchy rash on my arm for two days")["is_emergency"] is False


def test_rules_also_read_earlier_answers():
    """A red flag given in an earlier answer still counts."""
    state = {"symptoms": "chest discomfort", "answers": {"q": "yes, and I am sweating"}}
    assert triage.check_emergency("it spreads to my jaw", state)["is_emergency"] is True


def test_emergency_check_survives_empty_input():
    assert triage.check_emergency("")["is_emergency"] is False
    assert triage.check_emergency(None)["is_emergency"] is False


# --------------------------------------------------------- questioning floor


def test_ambiguous_symptoms_need_more_questions():
    assert triage.requires_deeper_questioning("I have chest pain") is True
    assert triage.minimum_questions({"symptoms": "chest pain"}) == 4


def test_specific_symptoms_need_fewer_questions():
    assert triage.requires_deeper_questioning("itchy rash on my arm") is False
    assert triage.minimum_questions({"symptoms": "itchy rash"}) == 2


def test_model_cannot_complete_before_the_floor():
    """The prototype would end a chest pain assessment after one answer."""
    state = {"symptoms": "chest pain", "question_count": 1}
    reasoning = {"assessment_complete": True, "urgency": "low"}
    assert triage.decide_next_step(state, reasoning) == "ask"


def test_model_may_complete_once_the_floor_is_met():
    state = {"symptoms": "chest pain", "question_count": 4}
    reasoning = {"assessment_complete": True, "urgency": "low"}
    assert triage.decide_next_step(state, reasoning) == "complete"


def test_hard_cap_ends_the_conversation():
    state = {"symptoms": "chest pain", "question_count": triage.MAX_QUESTIONS}
    reasoning = {"assessment_complete": False, "urgency": "low"}
    assert triage.decide_next_step(state, reasoning) == "complete"


def test_emergency_completes_immediately():
    state = {"symptoms": "chest pain", "question_count": 0}
    assert triage.decide_next_step(state, {"urgency": "emergency"}) == "complete"


def test_questions_are_not_repeated():
    state = {"asked": ["How long have you had these symptoms?"], "symptoms": "headache"}
    reasoning = {"follow_up_questions": ["How long have you had these symptoms?"]}
    assert triage.next_question(state, reasoning) != "How long have you had these symptoms?"


# ------------------------------------------------------------------- parsing


def test_extract_json_handles_surrounding_prose():
    assert triage.extract_json('Sure! {"urgency": "low"} hope that helps') == {"urgency": "low"}


def test_extract_json_returns_none_for_garbage():
    assert triage.extract_json("no json at all") is None
    assert triage.extract_json("") is None
    assert triage.extract_json(None) is None


def test_normaliser_falls_back_to_the_patients_own_words():
    result = triage.parse_normaliser(None, "  my  head   hurts ")
    assert result["symptoms"] == "my head hurts"


def test_reasoner_rejects_an_invalid_urgency():
    content = '{"urgency": "catastrophic", "likely_specialty": "Cardiologist"}'
    assert triage.parse_reasoner(content, {})["urgency"] == "low"


def test_reasoner_rejects_an_unknown_specialty():
    content = '{"likely_specialty": "Astrologer", "urgency": "low"}'
    assert triage.parse_reasoner(content, {})["likely_specialty"] == "General Physician"


def test_reasoner_accepts_a_case_insensitive_specialty():
    content = '{"likely_specialty": "cardiologist", "urgency": "low"}'
    assert triage.parse_reasoner(content, {})["likely_specialty"] == "Cardiologist"


def test_reasoner_falls_back_when_the_model_returns_nothing():
    result = triage.parse_reasoner(None, {"symptoms": "chest pain", "question_count": 0})
    assert result["degraded"] is True
    assert result["likely_specialty"] == "General Physician"
    assert result["assessment_complete"] is False


def test_fallback_never_claims_an_emergency():
    """A degraded assistant must not invent urgency it cannot assess."""
    assert triage.fallback_reasoning({})["urgency"] != "emergency"


def test_specialty_slug_matches_the_directory_format():
    assert triage.specialty_slug("ENT Specialist") == "ent-specialist"
