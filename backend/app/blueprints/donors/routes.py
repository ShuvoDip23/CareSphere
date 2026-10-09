"""Voluntary blood donor discovery and privacy-preserving contact requests."""

import re
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from ...extensions import db
from ...models.donor import BLOOD_GROUPS, BloodDonor, DonorRequest
from .validators import (
    ValidationError,
    validate_donor_registration,
    validate_donor_request,
)

donors_bp = Blueprint("donors", __name__, url_prefix="/api")

DEFAULT_PER_PAGE = 24
MAX_PER_PAGE = 100

BLOOD_COMPATIBILITY = {
    "O-": {
        "give": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
        "receive": ["O-"],
        "note": "Universal Red Cell Donor",
    },
    "O+": {
        "give": ["O+", "A+", "B+", "AB+"],
        "receive": ["O+", "O-"],
        "note": "Most commonly needed blood group",
    },
    "A-": {
        "give": ["A-", "A+", "AB-", "AB+"],
        "receive": ["A-", "O-"],
        "note": "Rare Rh-negative blood type",
    },
    "A+": {
        "give": ["A+", "AB+"],
        "receive": ["A+", "A-", "O+", "O-"],
        "note": "Second most common blood group",
    },
    "B-": {
        "give": ["B-", "B+", "AB-", "AB+"],
        "receive": ["B-", "O-"],
        "note": "Rare Rh-negative blood type",
    },
    "B+": {
        "give": ["B+", "AB+"],
        "receive": ["B+", "B-", "O+", "O-"],
        "note": "Highly prevalent in Bangladesh",
    },
    "AB-": {
        "give": ["AB-", "AB+"],
        "receive": ["AB-", "A-", "B-", "O-"],
        "note": "Very rare blood type",
    },
    "AB+": {
        "give": ["AB+"],
        "receive": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
        "note": "Universal Red Cell Recipient",
    },
}


def _int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


@donors_bp.get("/donors/compatibility")
def get_compatibility():
    """Return clinical blood compatibility matrix."""
    return jsonify(BLOOD_COMPATIBILITY)


@donors_bp.get("/donors/stats")
def get_donor_stats():
    """Return summary statistics of registered voluntary donors in Rajshahi."""
    total = BloodDonor.query.count()
    threshold = date.today() - timedelta(days=90)
    available = (
        BloodDonor.query.filter(BloodDonor.is_available.is_(True))
        .filter(
            or_(
                BloodDonor.last_donation_date.is_(None),
                BloodDonor.last_donation_date <= threshold,
            )
        )
        .count()
    )

    by_group = dict(
        db.session.query(BloodDonor.blood_group, func.count(BloodDonor.id))
        .group_by(BloodDonor.blood_group)
        .all()
    )

    return jsonify(
        {
            "total_donors": total,
            "available_donors": available,
            "by_group": {group: by_group.get(group, 0) for group in BLOOD_GROUPS},
        }
    )


@donors_bp.get("/donors")
def list_donors():
    """Search, filter, and paginate voluntary blood donors.

    Privacy Guarantee:
        Donor phone numbers and real names are excluded from public responses.
        Requesters contact donors securely via POST /api/donors/<id>/requests.

    Query parameters:
        q            Free text across area, nearby hospital, or donor ID (e.g. 'Kazla' or '101')
        blood_group  Blood group filter, e.g. 'O+' or 'A-'
        status       Availability filter: 'available' | 'eligible_soon' | 'unavailable'
        area         Area filter substring
        page         1-based page index (default 1)
        per_page     Page size (default 24, max 100)
    """
    query = BloodDonor.query

    blood_group = (request.args.get("blood_group") or "").strip().upper()
    if blood_group and blood_group in BLOOD_GROUPS:
        query = query.filter(BloodDonor.blood_group == blood_group)

    area = (request.args.get("area") or "").strip()
    if area:
        query = query.filter(BloodDonor.area.ilike(f"%{area}%"))

    search = (request.args.get("q") or "").strip()
    if search:
        search_lower = search.lower()
        id_match = re.search(r"(?:bd-?)?(\d+)", search_lower)
        conditions = [
            BloodDonor.area.ilike(f"%{search}%"),
            BloodDonor.hospital_near.ilike(f"%{search}%"),
            BloodDonor.blood_group.ilike(f"%{search}%"),
        ]
        if id_match:
            try:
                donor_num = int(id_match.group(1))
                conditions.append(BloodDonor.id == donor_num)
            except ValueError:
                pass
        query = query.filter(or_(*conditions))

    status = (request.args.get("status") or "").strip().lower()
    threshold = date.today() - timedelta(days=90)
    if status == "available":
        query = query.filter(BloodDonor.is_available.is_(True)).filter(
            or_(
                BloodDonor.last_donation_date.is_(None),
                BloodDonor.last_donation_date <= threshold,
            )
        )
    elif status == "eligible_soon":
        query = (
            query.filter(BloodDonor.is_available.is_(True))
            .filter(BloodDonor.last_donation_date.is_not(None))
            .filter(BloodDonor.last_donation_date > threshold)
        )
    elif status == "unavailable":
        query = query.filter(BloodDonor.is_available.is_(False))

    query = query.order_by(
        BloodDonor.is_available.desc(),
        BloodDonor.donations_count.desc(),
        BloodDonor.id.asc(),
    )

    page = _int_arg("page", 1, 1, 10_000)
    per_page = _int_arg("per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [donor.to_dict(public=True) for donor in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    )


@donors_bp.get("/donors/<int:donor_id>")
def get_donor(donor_id: int):
    """Retrieve public demographic info for a specific blood donor."""
    donor = db.session.get(BloodDonor, donor_id)
    if donor is None:
        return jsonify({"error": "Donor not found"}), 404
    return jsonify(donor.to_dict(public=True))


@donors_bp.post("/donors")
def register_donor():
    """Register as a voluntary blood donor in Rajshahi.

    Confidential phone number and full name are stored securely and never
    returned in public queries.
    """
    payload = request.get_json(silent=True) or {}
    try:
        cleaned = validate_donor_registration(payload)
    except ValidationError as err:
        return jsonify(
            {"error": "Please correct the highlighted fields", "fields": err.errors}
        ), 400

    donor = BloodDonor(
        name=cleaned["name"],
        blood_group=cleaned["blood_group"],
        area=cleaned["area"],
        phone=cleaned["phone"],
        hospital_near=cleaned.get("hospital_near"),
        last_donation_date=cleaned.get("last_donation_date"),
        is_available=cleaned.get("is_available", True),
    )

    db.session.add(donor)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Voluntary blood donor registered successfully.",
                "donor": donor.to_dict(public=True),
            }
        ),
        201,
    )


@donors_bp.post("/donors/<int:donor_id>/requests")
def request_donor_contact(donor_id: int):
    """Send a privacy-preserving urgent contact request to a donor.

    The requester's contact details and patient requirements are recorded and
    dispatched directly to the donor, keeping the donor's contact details confidential.
    """
    donor = db.session.get(BloodDonor, donor_id)
    if donor is None:
        return jsonify({"error": "Donor not found"}), 404

    payload = request.get_json(silent=True) or {}
    try:
        cleaned = validate_donor_request(payload)
    except ValidationError as err:
        return jsonify(
            {"error": "Please correct the highlighted fields", "fields": err.errors}
        ), 400

    contact_request = DonorRequest(
        donor_id=donor.id,
        patient_name=cleaned["patient_name"],
        hospital=cleaned["hospital"],
        units=cleaned["units"],
        urgency=cleaned["urgency"],
        requester_phone=cleaned["requester_phone"],
        notes=cleaned.get("notes"),
        status="pending",
    )

    db.session.add(contact_request)
    db.session.commit()

    return (
        jsonify(
            {
                "message": (
                    f"Secure contact request dispatched to Donor #{donor.display_id}. "
                    "The donor will be notified via SMS/App."
                ),
                "request": contact_request.to_dict(),
            }
        ),
        201,
    )
