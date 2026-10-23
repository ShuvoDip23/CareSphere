"""Registration, login, logout and session introspection."""

from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models.doctor import Doctor, DoctorAvailability, Specialty
from ...models.user import User
from ...utils.security import current_user
from ..admin.validators import MIN_PASSWORD_LENGTH, ValidationError, validate_application

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


def _start_session(user: User) -> None:
    session.clear()
    session["user_id"] = user.id


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    name = str(data.get("name") or "").strip()
    password = data.get("password") or ""

    if not email or not name or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify(
            {"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}
        ), 400

    # Role is never taken from the request body. Doctor and provider accounts
    # are ported in weeks 2 and 4 and go through an approval flow.
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(email=email, name=name, role=User.ROLE_PATIENT)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    _start_session(user)
    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        # Same message either way, so the endpoint cannot be used to
        # enumerate registered email addresses.
        return jsonify({"error": "Invalid email or password"}), 401

    _start_session(user)
    return jsonify({"message": "Login successful", "user": user.to_dict()}), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.get("/me")
def me():
    user = current_user()
    if user is None:
        session.clear()
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user.to_dict()}), 200


@auth_bp.post("/register/doctor")
def register_doctor():
    """Apply for a doctor account.

    Creates the account, the profile and the link between them in one
    transaction. A half-made application - an account with no profile, or a
    profile nobody can sign in to - is worse than no application at all, so
    either all three land or none do.

    The profile starts at `pending` and is invisible to patients until an
    administrator approves it. `approval_status` is never read from the
    request body, for the same reason `/api/register` never reads `role`.
    """
    try:
        account, profile, windows = validate_application(request.get_json(silent=True) or {})
    except ValidationError as error:
        return jsonify(
            {"error": "Please correct the highlighted fields", "fields": error.errors}
        ), 400

    if User.query.filter_by(email=account["email"]).first():
        return jsonify(
            {
                "error": "Please correct the highlighted fields",
                "fields": {"email": "Email already registered"},
            }
        ), 400

    user = User(email=account["email"], name=account["name"], role=User.ROLE_DOCTOR)
    user.set_password(account["password"])
    db.session.add(user)
    db.session.flush()

    specialty_name = profile.pop("specialty")
    doctor = Doctor(
        **profile,
        specialty=Specialty.get_or_create(specialty_name),
        user_id=user.id,
        approval_status=Doctor.STATUS_PENDING,
    )
    db.session.add(doctor)
    db.session.flush()

    for window in windows:
        db.session.add(DoctorAvailability(doctor_id=doctor.id, **window))

    try:
        db.session.commit()
    except IntegrityError:
        # Two applications racing on the same email, or on the one-profile-
        # per-account constraint. The database decides; the loser is told.
        db.session.rollback()
        return jsonify({"error": "That email is already registered"}), 409

    _start_session(user)
    return jsonify(
        {
            "message": "Application submitted",
            "user": user.to_dict(),
            "doctor": doctor.to_dict(include_availability=True),
        }
    ), 201
