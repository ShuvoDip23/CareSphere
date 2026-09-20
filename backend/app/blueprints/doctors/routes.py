"""Public doctor discovery endpoints.

All reads. Nothing here writes to the database - the prototype's availability
endpoint inserted 56 rows on an unauthenticated GET, which made a read request
non-idempotent and gave anyone a cheap way to grow the database.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from ...extensions import db
from ...models.doctor import Doctor, Specialty

doctors_bp = Blueprint("doctors", __name__, url_prefix="/api")

MAX_PER_PAGE = 48
DEFAULT_PER_PAGE = 12
SORT_OPTIONS = {
    "rating": (Doctor.rating.desc(), Doctor.review_count.desc()),
    "experience": (Doctor.experience_years.desc(),),
    "fee_low": (Doctor.fee.asc(),),
    "fee_high": (Doctor.fee.desc(),),
    "name": (Doctor.name.asc(),),
}


def _int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


@doctors_bp.get("/specialties")
def list_specialties():
    """Specialties that have at least one approved doctor, with counts."""
    rows = (
        db.session.query(Specialty, func.count(Doctor.id))
        .join(Doctor, Doctor.specialty_id == Specialty.id)
        .filter(Doctor.approval_status == Doctor.STATUS_APPROVED)
        .group_by(Specialty.id)
        .order_by(Specialty.name.asc())
        .all()
    )
    return jsonify([specialty.to_dict(doctor_count=count) for specialty, count in rows])


@doctors_bp.get("/doctors")
def list_doctors():
    """Search, filter, sort and paginate approved doctors.

    Query parameters
        q          free text across name, hospital and location
        specialty  specialty slug, e.g. `ent-specialist`
        sort       rating | experience | fee_low | fee_high | name
        page       1-based
        per_page   1..48
    """
    query = Doctor.query.join(Specialty).filter(Doctor.approval_status == Doctor.STATUS_APPROVED)

    specialty_slug = (request.args.get("specialty") or "").strip().lower()
    if specialty_slug:
        query = query.filter(Specialty.slug == specialty_slug)

    search = (request.args.get("q") or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Doctor.name.ilike(pattern),
                Doctor.hospital.ilike(pattern),
                Doctor.location.ilike(pattern),
                Specialty.name.ilike(pattern),
            )
        )

    sort_key = (request.args.get("sort") or "rating").lower()
    query = query.order_by(*SORT_OPTIONS.get(sort_key, SORT_OPTIONS["rating"]))

    page = _int_arg("page", 1, 1, 10_000)
    per_page = _int_arg("per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [doctor.to_dict() for doctor in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    )


@doctors_bp.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id: int):
    doctor = Doctor.query.filter_by(id=doctor_id, approval_status=Doctor.STATUS_APPROVED).first()
    if doctor is None:
        # Pending and rejected profiles are indistinguishable from missing ones,
        # so the endpoint cannot be used to enumerate unapproved applications.
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify(doctor.to_dict(include_availability=True))
