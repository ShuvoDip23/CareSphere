"""Input cleaning and validation for the admin console.

Kept out of routes.py so the rules can be unit-tested without HTTP, and so the
doctor self-registration flow in week 2 can reuse exactly the same validation.
"""

from ...models.doctor import DAY_NAMES

MAX_FEE = 100_000
MAX_EXPERIENCE = 70
APPROVAL_STATUSES = ("pending", "approved", "rejected")


class ValidationError(ValueError):
    """Raised with a field-keyed dict so the UI can highlight the right input."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("Validation failed")
        self.errors = errors


def clean_text(value, max_length: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:max_length] if text else None


def _number(errors, data, key, label, caster, minimum, maximum, default=None):
    raw = data.get(key, default)
    if raw is None or raw == "":
        errors[key] = f"{label} is required"
        return None
    try:
        value = caster(raw)
    except (TypeError, ValueError):
        errors[key] = f"{label} must be a number"
        return None
    if value < minimum or value > maximum:
        errors[key] = f"{label} must be between {minimum} and {maximum}"
        return None
    return value


def validate_doctor(data: dict, partial: bool = False) -> dict:
    """Return a cleaned payload, or raise ValidationError.

    `partial=True` allows an update that omits fields, leaving them unchanged.
    """
    if not isinstance(data, dict):
        raise ValidationError({"_": "Request body must be a JSON object"})

    errors: dict[str, str] = {}
    cleaned: dict = {}

    text_fields = [
        ("name", "Doctor name", 120),
        ("specialty", "Specialty", 80),
        ("hospital", "Hospital", 200),
        ("location", "Location", 200),
        ("phone", "Phone number", 30),
    ]
    for key, label, length in text_fields:
        if partial and key not in data:
            continue
        value = clean_text(data.get(key), length)
        if not value:
            errors[key] = f"{label} is required"
        else:
            cleaned[key] = value

    for key, length in (("qualification", 240), ("bio", 1000)):
        if key in data:
            cleaned[key] = clean_text(data.get(key), length)

    if not partial or "fee" in data:
        fee = _number(errors, data, "fee", "Consultation fee", float, 0, MAX_FEE)
        if fee is not None:
            cleaned["fee"] = fee

    if not partial or "experience_years" in data:
        years = _number(
            errors, data, "experience_years", "Years of experience", int, 0, MAX_EXPERIENCE, 0
        )
        if years is not None:
            cleaned["experience_years"] = years

    if "rating" in data and data["rating"] not in (None, ""):
        rating = _number(errors, data, "rating", "Rating", float, 0, 5)
        if rating is not None:
            cleaned["rating"] = rating

    if "review_count" in data and data["review_count"] not in (None, ""):
        reviews = _number(errors, data, "review_count", "Review count", int, 0, 1_000_000)
        if reviews is not None:
            cleaned["review_count"] = reviews

    if "approval_status" in data:
        status = str(data.get("approval_status") or "").strip().lower()
        if status not in APPROVAL_STATUSES:
            errors["approval_status"] = "Status must be pending, approved or rejected"
        else:
            cleaned["approval_status"] = status

    if "rejection_note" in data:
        cleaned["rejection_note"] = clean_text(data.get("rejection_note"), 500)

    if errors:
        raise ValidationError(errors)
    return cleaned


def _valid_time(value) -> str | None:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def validate_availability(data: dict) -> list[dict]:
    """Accept a list of {day_of_week, start_time, end_time} and normalise it."""
    rows = data.get("availability") if isinstance(data, dict) else None
    if rows is None:
        raise ValidationError({"availability": "availability must be a list"})
    if not isinstance(rows, list):
        raise ValidationError({"availability": "availability must be a list"})

    errors: dict[str, str] = {}
    cleaned: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors[f"availability.{index}"] = "Each entry must be an object"
            continue
        try:
            day = int(row.get("day_of_week"))
        except (TypeError, ValueError):
            errors[f"availability.{index}"] = "day_of_week must be 0-6"
            continue
        if not 0 <= day <= 6:
            errors[f"availability.{index}"] = "day_of_week must be 0-6"
            continue

        start = _valid_time(row.get("start_time"))
        end = _valid_time(row.get("end_time"))
        if not start or not end:
            errors[f"availability.{index}"] = "Times must be in HH:MM format"
            continue
        if start >= end:
            errors[f"availability.{index}"] = (
                f"{DAY_NAMES[day]} end time must be after the start time"
            )
            continue

        key = (day, start)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"day_of_week": day, "start_time": start, "end_time": end})

    if errors:
        raise ValidationError(errors)
    return cleaned
