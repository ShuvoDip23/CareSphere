"""Triage rules, prompts and conversation flow.

Pure logic: no HTTP, no database, no Flask. Every function here is directly
unit-testable, which is what makes the safety rules verifiable rather than
merely present. The blueprint orchestrates; this module decides.
"""

import json
import re

MAX_QUESTIONS = 5
MIN_QUESTIONS_DEFAULT = 2
MIN_QUESTIONS_AMBIGUOUS = 4

URGENCY_LEVELS = ("low", "medium", "high", "emergency")

SPECIALTIES = (
    "Cardiologist",
    "Dermatologist",
    "ENT Specialist",
    "Neurologist",
    "Orthopedic",
    "Gastroenterologist",
    "Pulmonologist",
    "Ophthalmologist",
    "General Physician",
    "Emergency Medicine",
)

DISCLAIMER = (
    "This is not a medical diagnosis. CareSphere helps you decide which kind of "
    "doctor to see. Please consult a qualified healthcare professional."
)

# --------------------------------------------------------------------- safety

# Phrases that on their own warrant immediate escalation.
EMERGENCY_PATTERNS = (
    r"\b(can'?t breathe|cannot breathe|not breathing|struggling to breathe)\b",
    # Chest symptoms referring to the arm, jaw or shoulder, in either order.
    r"\bchest (pain|discomfort|tightness|pressure)\b.{0,40}\b(left arm|jaw|shoulder|sweat)",
    r"\b(left arm|jaw|shoulder|sweat)\w*\b.{0,40}\bchest (pain|discomfort|tightness|pressure)\b",
    r"\b(crushing|severe) chest (pain|pressure|tightness)\b",
    r"\b(fainted|passed out|unconscious|unresponsive)\b",
    r"\bstroke\b",
    # "slurred speech" and "speech is slurred" both have to match.
    r"\b(slurred speech|speech (is |was )?slurred)\b",
    r"\b(face (is |was )?drooping|face drooping|drooping face)\b",
    r"\bone[- ]sided weakness\b",
    r"\b(seizure|convulsion|fitting)\b",
    r"\b(coughing up blood|vomiting blood|blood in stool|bleeding heavily)\b",
    r"\bsudden (vision loss|blindness|loss of vision)\b",
    # "throat closing", "throat is closing up", "my throat closes".
    r"\bthroat (is |was )?clos\w+",
    r"\b(swollen tongue|severe allergic reaction|anaphylaxis)\b",
    r"\b(suicidal|kill myself|end my life)\b",
)

# Individually ambiguous, but two or more together are a red flag.
RED_FLAG_TERMS = (
    "shortness of breath",
    "short of breath",
    "left arm",
    "jaw",
    "fainting",
    "dizzy and weak",
    "slurred speech",
    "blood in stool",
    "vomiting blood",
    "sudden vision loss",
    "severe weakness",
    "cold sweat",
    "sweating",
    "crushing chest pain",
    "irregular heartbeat",
    "very high fever",
    "stiff neck",
    "confusion",
)

# Presentations where a single answer is never enough to conclude.
AMBIGUOUS_SYMPTOMS = (
    "chest pain",
    "abdominal pain",
    "stomach pain",
    "headache",
    "dizziness",
    "dizzy",
    "shortness of breath",
    "breathing",
    "back pain",
    "fainting",
    "weakness",
    "numbness",
    "palpitations",
)

GENERIC_QUESTIONS = (
    "How long have you had these symptoms?",
    "How severe would you call them - mild, moderate or severe?",
    "Do you also have fever, shortness of breath, vomiting or severe weakness?",
    "Does anything make them better or worse - movement, eating, or rest?",
)

EMERGENCY_ACTIONS = (
    "Go to the nearest emergency department now, or call local emergency services.",
    "Do not drive yourself if you feel faint, breathless or confused.",
    "Take someone with you if you can, and bring any medicines you are taking.",
)


def normalise(text: str | None) -> str:
    return " ".join(str(text or "").strip().lower().split())


def check_emergency(text: str, state: dict | None = None) -> dict:
    """Rule-based escalation that runs independently of the language model.

    This is the safety net: if the model is unavailable, slow, or simply wrong,
    these rules still fire. They are intentionally conservative.
    """
    state = state or {}
    haystacks = [normalise(text), normalise(state.get("symptoms"))]
    answers = state.get("answers")
    if isinstance(answers, dict):
        haystacks.extend(normalise(value) for value in answers.values())
    combined = " ".join(h for h in haystacks if h)

    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, combined):
            return {
                "is_emergency": True,
                "reason": "Your message mentions a warning sign that needs urgent assessment.",
                "matched_by": "pattern",
            }

    hits = sorted({term for term in RED_FLAG_TERMS if term in combined})
    if len(hits) >= 2:
        return {
            "is_emergency": True,
            "reason": "Several warning signs appear together: " + ", ".join(hits[:4]) + ".",
            "matched_by": "red_flags",
        }

    return {"is_emergency": False, "reason": "", "matched_by": None}


def requires_deeper_questioning(text: str) -> bool:
    haystack = normalise(text)
    return any(symptom in haystack for symptom in AMBIGUOUS_SYMPTOMS)


def minimum_questions(state: dict) -> int:
    if requires_deeper_questioning(state.get("symptoms", "")):
        return MIN_QUESTIONS_AMBIGUOUS
    return MIN_QUESTIONS_DEFAULT


# -------------------------------------------------------------------- prompts

NORMALISER_SYSTEM = """
You normalise patient descriptions for a healthcare triage assistant.

Tasks:
1. Correct obvious spelling mistakes.
2. Rewrite the message in plain clinical English.
3. Extract short symptom phrases.
4. Extract duration, severity and body location if the patient mentioned them.

Rules:
- Do NOT diagnose.
- Do NOT invent symptoms the patient did not describe.
- Patients may write informally, or mix English with another language. Preserve
  their meaning exactly; translate rather than reinterpret.
- Leave a field as an empty string when the patient did not mention it.
- Reply with JSON only, using exactly this schema:

{"normalized_text": "...", "symptoms": ["..."], "duration": "", "severity": "", "body_location": ""}
""".strip()

REASONER_SYSTEM = """
You are a cautious triage reasoning assistant for an academic symptom checker.
You do NOT diagnose. You decide which kind of doctor the patient should see.

You must:
1. Consider several possible causes, not one.
2. Ask only follow-up questions that would change the recommendation.
3. Recommend a likely specialty.
4. Identify warning signs worth watching for.
5. Decide whether you have enough information.

Rules:
- Be conservative. Never claim certainty.
- Never invent information the patient has not given.
- Ask at most 3 follow-up questions at a time, phrased simply.
- urgency must be exactly one of: low, medium, high, emergency.
- likely_specialty must be one of: {specialties}.
- For ambiguous complaints (chest pain, abdominal pain, headache, dizziness,
  fainting, weakness, breathing difficulty) ask at least 3-4 discriminating
  questions before completing, unless emergency signs are already present.
- For chest pain specifically, ask about radiation, breathlessness, sweating,
  nausea, relation to exertion or food, and the character of the pain before
  concluding. Distinguish cardiac, gastric, respiratory, musculoskeletal and
  anxiety-related causes.

Reply with JSON only, using exactly this schema:

{{"possible_conditions": [{{"name": "...", "likelihood": "low|medium|high"}}],
 "red_flags": ["..."],
 "follow_up_questions": ["..."],
 "likely_specialty": "...",
 "urgency": "low|medium|high|emergency",
 "assessment_complete": true,
 "summary": "..."}}
""".strip()


def build_normaliser_messages(user_text: str) -> list[dict]:
    return [
        {"role": "system", "content": NORMALISER_SYSTEM},
        {"role": "user", "content": f"Patient message: {user_text}"},
    ]


def build_reasoner_messages(state: dict) -> list[dict]:
    payload = {
        "symptoms": state.get("symptoms", ""),
        "duration": state.get("duration", ""),
        "severity": state.get("severity", ""),
        "body_location": state.get("body_location", ""),
        "answers": state.get("answers", {}),
        "questions_asked": state.get("asked", []),
        "question_count": state.get("question_count", 0),
    }
    return [
        {
            "role": "system",
            "content": REASONER_SYSTEM.format(specialties=", ".join(SPECIALTIES)),
        },
        {"role": "user", "content": json.dumps(payload)},
    ]


# --------------------------------------------------------------------- parsing


def extract_json(content: str | None) -> dict | None:
    """Pull a JSON object out of a model reply, tolerating prose around it."""
    if not content:
        return None
    text = content.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [" ".join(str(v).split()) for v in value if str(v).strip()]
    return items[:limit]


def parse_normaliser(content: str | None, raw_text: str) -> dict:
    """Always returns a usable structure; falls back to the patient's own words."""
    parsed = extract_json(content) or {}
    normalized = " ".join(str(parsed.get("normalized_text") or "").split())
    return {
        "symptoms": normalized or " ".join(raw_text.split()),
        "symptom_list": _clean_list(parsed.get("symptoms"), 8),
        "duration": " ".join(str(parsed.get("duration") or "").split()),
        "severity": " ".join(str(parsed.get("severity") or "").split()),
        "body_location": " ".join(str(parsed.get("body_location") or "").split()),
    }


def fallback_reasoning(state: dict) -> dict:
    """Used when the model is unavailable. Never completes early, never guesses."""
    count = state.get("question_count", 0)
    return {
        "possible_conditions": [{"name": "Needs clinical assessment", "likelihood": "medium"}],
        "red_flags": [],
        "follow_up_questions": [],
        "likely_specialty": "General Physician",
        "urgency": "medium",
        "assessment_complete": count >= minimum_questions(state),
        "summary": (
            "The AI assistant is unavailable, so this is a general recommendation only. "
            "A general physician can assess your symptoms and refer you onward."
        ),
        "degraded": True,
    }


def parse_reasoner(content: str | None, state: dict) -> dict:
    parsed = extract_json(content)
    if parsed is None:
        return fallback_reasoning(state)

    conditions = []
    for item in parsed.get("possible_conditions") or []:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "").split())
        if not name:
            continue
        likelihood = str(item.get("likelihood") or "medium").lower()
        if likelihood not in ("low", "medium", "high"):
            likelihood = "medium"
        conditions.append({"name": name[:120], "likelihood": likelihood})

    urgency = str(parsed.get("urgency") or "low").lower()
    if urgency not in URGENCY_LEVELS:
        urgency = "low"

    specialty = " ".join(str(parsed.get("likely_specialty") or "").split())
    if specialty not in SPECIALTIES:
        # Accept a close match before giving up, e.g. "cardiologist".
        lowered = specialty.lower()
        specialty = next(
            (s for s in SPECIALTIES if s.lower() == lowered),
            "General Physician",
        )

    return {
        "possible_conditions": conditions[:4] or fallback_reasoning(state)["possible_conditions"],
        "red_flags": _clean_list(parsed.get("red_flags"), 5),
        "follow_up_questions": _clean_list(parsed.get("follow_up_questions"), 3),
        "likely_specialty": specialty,
        "urgency": urgency,
        "assessment_complete": bool(parsed.get("assessment_complete", False)),
        "summary": " ".join(str(parsed.get("summary") or "").split())[:600]
        or "Your symptoms should be reviewed by a doctor.",
        "degraded": False,
    }


# ----------------------------------------------------------------------- flow


def emergency_reasoning(reason: str) -> dict:
    return {
        "possible_conditions": [{"name": "Possible medical emergency", "likelihood": "high"}],
        "red_flags": [reason],
        "follow_up_questions": [],
        "likely_specialty": "Emergency Medicine",
        "urgency": "emergency",
        "assessment_complete": True,
        "summary": reason,
        "degraded": False,
    }


def decide_next_step(state: dict, reasoning: dict) -> str:
    """Return "ask" or "complete", enforcing the minimum-questions floor.

    The model's own `assessment_complete` is advisory. It cannot shortcut the
    floor, which is what stops a single answer like "sharp" from ending a chest
    pain assessment.
    """
    if reasoning.get("urgency") == "emergency":
        return "complete"

    asked = state.get("question_count", 0)
    if asked >= MAX_QUESTIONS:
        return "complete"
    if reasoning.get("assessment_complete") and asked >= minimum_questions(state):
        return "complete"
    return "ask"


def next_question(state: dict, reasoning: dict) -> str:
    """Prefer the model's question; fall back to a generic one that is not a repeat."""
    asked = [normalise(q) for q in state.get("asked", [])]
    for question in reasoning.get("follow_up_questions", []):
        if normalise(question) not in asked:
            return question
    for question in GENERIC_QUESTIONS:
        if normalise(question) not in asked:
            return question
    return GENERIC_QUESTIONS[-1]


def next_steps_for(specialty: str, urgency: str) -> list[str]:
    steps = [f"Consider booking an appointment with a {specialty}."]
    if urgency == "high":
        steps.append("Try to be seen within the next day or two.")
    elif urgency == "medium":
        steps.append("Book an appointment soon rather than waiting for it to pass.")
    else:
        steps.append("If symptoms persist or worsen, book an appointment.")
    steps.append("Seek urgent care immediately if any warning sign below appears.")
    return steps


def specialty_slug(specialty: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(specialty or "").lower()).strip("-")
