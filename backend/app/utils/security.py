"""Authentication and authorisation helpers.

Roles are resolved from the database on every request rather than trusted from
the session. In the old project the role was copied into the session at login,
so promoting a user required them to log out and back in, and a demoted admin
kept admin rights until their session expired.
"""

from functools import wraps

from flask import jsonify, request, session

from ..extensions import db
from ..models.user import User


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 204
        if current_user() is None:
            session.clear()
            return jsonify({"error": "Login required"}), 401
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles: str):
    """Allow the request only if the DB-backed role is one of `roles`."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if request.method == "OPTIONS":
                return "", 204
            user = current_user()
            if user is None:
                session.clear()
                return jsonify({"error": "Login required"}), 401
            if user.role not in roles:
                return jsonify({"error": "You do not have access to this resource"}), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator


admin_required = roles_required(User.ROLE_ADMIN)
patient_required = roles_required(User.ROLE_PATIENT)
