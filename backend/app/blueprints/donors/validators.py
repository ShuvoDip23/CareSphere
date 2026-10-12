"""Input cleaning and validation for voluntary blood donors and contact requests."""

import re
from datetime import date, datetime

from ...models.donor import BLOOD_GROUPS, URGENCY_LEVELS

PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,25}$")


class ValidationError(ValueError):
    """Raised with field-keyed errors so the UI can highlight the right inputs."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("Validation failed")
        self.errors = errors


def clean_text(value, max_length: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:max_length] if text else None


def validate_donor_registration(data: dict) -> dict:
    """Validate voluntary blood donor registration payload."""
    if not isinstance(data, dict):
        raise ValidationError({"_": "Request body must be a JSON object"})

    errors: dict[str, str] = {}
    cleaned: dict = {}

    # Name
    name = clean_text(data.get("name"), 100)
    if not name or len(name) < 2:
        errors["name"] = "Full name is required (at least 2 characters)"
    else:
        cleaned["name"] = name

    # Blood group
    blood_group = str(data.get("blood_group") or "").strip().upper()
    if not blood_group:
        errors["blood_group"] = "Blood group is required"
    elif blood_group not in BLOOD_GROUPS:
        errors["blood_group"] = f"Invalid blood group. Must be one of: {', '.join(BLOOD_GROUPS)}"
    else:
        cleaned["blood_group"] = blood_group

    # Area
    area = clean_text(data.get("area"), 120)
    if not area or len(area) < 2:
        errors["area"] = "Area in Rajshahi is required"
    else:
        cleaned["area"] = area

    # Phone
    phone = str(data.get("phone") or "").strip()
    if not phone:
        errors["phone"] = "Contact phone number is required"
    elif not PHONE_RE.match(phone):
        errors["phone"] = "Please enter a valid phone number (e.g. +8801700000000)"
    else:
        cleaned["phone"] = phone

    # Hospital / Nearby landmark
    hospital_near = clean_text(data.get("hospital_near"), 200)
    cleaned["hospital_near"] = hospital_near

    # Last donation date
    raw_date = data.get("last_donation_date")
    if raw_date:
        try:
            parsed_date = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
            if parsed_date > date.today():
                errors["last_donation_date"] = "Last donation date cannot be in the future"
            else:
                cleaned["last_donation_date"] = parsed_date
        except ValueError:
            errors["last_donation_date"] = "Date must be in YYYY-MM-DD format"
    else:
        cleaned["last_donation_date"] = None

    # Availability
    is_available = data.get("is_available", True)
    cleaned["is_available"] = bool(is_available)

    if errors:
        raise ValidationError(errors)

    return cleaned


def validate_donor_request(data: dict) -> dict:
    """Validate contact request payload dispatched to a donor."""
    if not isinstance(data, dict):
        raise ValidationError({"_": "Request body must be a JSON object"})

    errors: dict[str, str] = {}
    cleaned: dict = {}

    patient_name = clean_text(data.get("patient_name"), 100)
    if not patient_name or len(patient_name) < 2:
        errors["patient_name"] = "Patient name is required (at least 2 characters)"
    else:
        cleaned["patient_name"] = patient_name

    hospital = clean_text(data.get("hospital"), 200)
    if not hospital or len(hospital) < 2:
        errors["hospital"] = "Hospital or delivery location is required"
    else:
        cleaned["hospital"] = hospital

    raw_units = data.get("units", 1)
    try:
        units = int(raw_units)
        if units < 1 or units > 10:
            errors["units"] = "Units needed must be between 1 and 10"
        else:
            cleaned["units"] = units
    except (TypeError, ValueError):
        errors["units"] = "Units needed must be a number"

    urgency = str(data.get("urgency") or "emergency").strip().lower()
    if urgency not in URGENCY_LEVELS:
        errors["urgency"] = f"Urgency must be one of: {', '.join(URGENCY_LEVELS)}"
    else:
        cleaned["urgency"] = urgency

    requester_phone = str(data.get("requester_phone") or "").strip()
    if not requester_phone:
        errors["requester_phone"] = "Attendant contact phone is required"
    elif not PHONE_RE.match(requester_phone):
        errors["requester_phone"] = "Please enter a valid phone number"
    else:
        cleaned["requester_phone"] = requester_phone

    notes = clean_text(data.get("notes"), 500)
    cleaned["notes"] = notes

    if errors:
        raise ValidationError(errors)

    return cleaned
