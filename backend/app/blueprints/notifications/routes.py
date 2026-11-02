"""User-scoped notification inbox.

`login_required`, not `patient_required`: booking an appointment only requires
a login, so a doctor can book, pay, and have a confirmation notification
created for them. Restricting the inbox to patients made those unreadable.
Every query is still scoped to `current_user().id`.
"""

from datetime import UTC, datetime

from flask import Blueprint, jsonify

from ...extensions import db
from ...models.notification import Notification
from ...utils.security import current_user, login_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.get("")
@login_required
def list_notifications():
    rows = (
        Notification.query.filter_by(patient_id=current_user().id)
        .order_by(Notification.created_at.desc())
        .limit(200)
        .all()
    )
    unread = Notification.query.filter_by(patient_id=current_user().id, read_at=None).count()
    return jsonify({"notifications": [n.to_dict() for n in rows], "unread_count": unread})


@notifications_bp.patch("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    row = Notification.query.filter_by(id=notification_id, patient_id=current_user().id).first()
    if not row:
        return jsonify({"error": "Notification not found"}), 404
    row.read_at = row.read_at or datetime.now(UTC)
    db.session.commit()
    return jsonify({"notification": row.to_dict()})


@notifications_bp.post("/read-all")
@login_required
def mark_all_read():
    Notification.query.filter_by(patient_id=current_user().id, read_at=None).update(
        {"read_at": datetime.now(UTC)}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({"message": "All notifications marked as read"})


@notifications_bp.delete("/<int:notification_id>")
@login_required
def delete_notification(notification_id):
    row = Notification.query.filter_by(id=notification_id, patient_id=current_user().id).first()
    if not row:
        return jsonify({"error": "Notification not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Notification deleted"})
