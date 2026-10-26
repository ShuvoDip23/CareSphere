"""Payment endpoints.

Three ways a payment can come back from SSLCommerz, and only one of them is
trustworthy:

* **IPN** - posted server to server. The patient's browser is not involved,
  so it arrives even if they close the tab the moment they pay. Authoritative.
* **The success redirect** - the patient's browser returns carrying query
  parameters. Convenient, and the only thing that works on localhost, but it
  is a message from the patient's machine, not from SSLCommerz.
* **fail / cancel redirects** - the same, for the unhappy paths.

All three land in `_settle`, which ignores what the caller said happened and
asks SSLCommerz directly. That is the difference from the prototype, where
the success redirect was believed on its own and could be forged by hand.
"""

import secrets
from datetime import UTC, datetime, timedelta

from flask import Blueprint, current_app, jsonify, redirect, request

from ...extensions import db
from ...models.appointment import Appointment
from ...models.payment import PaymentAttempt
from ...services import payments, sslcommerz
from ...utils.security import current_user, login_required

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def _frontend(path: str) -> str:
    origins = current_app.config.get("FRONTEND_ORIGINS") or ["http://127.0.0.1:5500"]
    return f"{origins[0].rstrip('/')}/{path.lstrip('/')}"


def _callback_urls() -> dict:
    base = current_app.config["PUBLIC_BASE_URL"]
    return {
        "success": f"{base}/api/payments/return/success",
        "fail": f"{base}/api/payments/return/fail",
        "cancel": f"{base}/api/payments/return/cancel",
        "ipn": f"{base}/api/payments/ipn",
    }


def _hold_expired(appointment: Appointment) -> bool:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=payments.HOLD_MINUTES)
    return appointment.created_at.replace(tzinfo=None) < cutoff


def release_expired_holds() -> int:
    """Hand back slots held by payments nobody finished.

    Runs on booking and on the slot listing rather than from a scheduler,
    because the only moment the answer matters is when somebody is looking at
    that day's availability. The row stays for the patient's history; only
    `slot_key` is cleared, the same mechanism as cancelling.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=payments.HOLD_MINUTES)
    stale = Appointment.query.filter(
        Appointment.status == Appointment.STATUS_PENDING_PAYMENT,
        Appointment.payment_status == Appointment.PAYMENT_UNPAID,
        Appointment.slot_key.isnot(None),
        Appointment.created_at < cutoff,
    ).all()

    for appointment in stale:
        appointment.release_slot()
        appointment.status = Appointment.STATUS_CANCELLED
        appointment.cancelled_at = datetime.now(UTC)
    if stale:
        db.session.commit()
    return len(stale)


# ------------------------------------------------------------- settlement


def _settle(val_id: str, transaction_id: str, via: str) -> tuple[Appointment | None, str | None]:
    """Verify one transaction against SSLCommerz and record the outcome.

    Idempotent: IPN and the redirect routinely both arrive for the same
    payment, and a patient who refreshes the return page sends a third. The
    first one settles it; the rest find it already paid and change nothing.
    """
    attempt = PaymentAttempt.query.filter_by(transaction_id=transaction_id).first()
    if attempt is None:
        return None, "We could not find that payment."

    appointment = attempt.appointment
    if attempt.is_settled and appointment.is_paid:
        return appointment, None

    try:
        validation = sslcommerz.validate(val_id)
    except sslcommerz.GatewayError as error:
        # Reaching the gateway failed, which is not the same as the payment
        # failing. The attempt is left open so a retry or the IPN can settle
        # it, rather than being written off as failed.
        return appointment, str(error)

    try:
        verified = payments.verify(
            validation,
            expected_amount=attempt.amount,
            expected_tran_id=attempt.transaction_id,
        )
    except payments.Rejected as rejection:
        attempt.status = PaymentAttempt.STATUS_FAILED
        attempt.failure_reason = str(rejection)
        appointment.payment_status = Appointment.PAYMENT_FAILED
        db.session.commit()
        return appointment, str(rejection)

    attempt.status = PaymentAttempt.STATUS_PAID
    attempt.val_id = verified["val_id"]
    attempt.card_type = verified["card_type"]
    attempt.bank_tran_id = verified["bank_tran_id"]
    attempt.settled_via = via
    attempt.settled_at = datetime.now(UTC)
    attempt.failure_reason = None

    appointment.payment_status = Appointment.PAYMENT_PAID
    appointment.status = Appointment.STATUS_CONFIRMED
    appointment.transaction_id = attempt.transaction_id
    appointment.payment_method = verified["card_type"]
    db.session.commit()
    return appointment, None


# ---------------------------------------------------------------- routes


@payments_bp.post("/appointments/<int:appointment_id>/session")
@login_required
def open_session(appointment_id: int):
    """Open a checkout for an appointment the signed-in patient owns."""
    user = current_user()
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.user_id != user.id:
        return jsonify({"error": "Appointment not found"}), 404

    if appointment.is_paid:
        return jsonify({"error": "This appointment is already paid for."}), 409
    if appointment.is_cancelled:
        return jsonify({"error": "This appointment was cancelled."}), 409
    if appointment.is_past:
        return jsonify({"error": "This appointment has already passed."}), 409
    if appointment.slot_key is None or _hold_expired(appointment):
        return jsonify(
            {"error": "This slot was released because it was not paid for in time."}
        ), 409
    if not sslcommerz.is_configured():
        return jsonify({"error": "Online payment is not configured on this server."}), 503

    # A fresh transaction id per attempt: reusing one lets a second attempt be
    # settled against the first attempt's validation record.
    attempt = PaymentAttempt(
        appointment_id=appointment.id,
        transaction_id=payments.build_transaction_id(appointment.id, secrets.token_hex(6)),
        amount=appointment.fee_at_booking,
    )
    db.session.add(attempt)
    db.session.flush()

    try:
        session = sslcommerz.start_session(
            transaction_id=attempt.transaction_id,
            amount=appointment.fee_at_booking,
            appointment=appointment,
            patient=user,
            urls=_callback_urls(),
        )
    except sslcommerz.GatewayError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 502

    attempt.session_key = session.get("session_key")
    db.session.commit()

    return jsonify(
        {
            "gateway_url": session["gateway_url"],
            "transaction_id": attempt.transaction_id,
            "amount": float(attempt.amount),
        }
    ), 201


@payments_bp.post("/ipn")
def ipn():
    """SSLCommerz's own notification. The authoritative confirmation.

    Unauthenticated by nature - SSLCommerz has no session here - which is
    exactly why nothing in the body is believed. The `val_id` is used only to
    ask SSLCommerz what happened; every figure is then read from that answer.
    """
    body = request.form.to_dict() or (request.get_json(silent=True) or {})
    transaction_id = str(body.get("tran_id") or "").strip()
    val_id = str(body.get("val_id") or "").strip()

    appointment, error = _settle(val_id, transaction_id, PaymentAttempt.VIA_IPN)
    if appointment is None:
        return jsonify({"status": "unknown transaction"}), 404
    # 200 either way: SSLCommerz retries on a non-200, and retrying will not
    # change a payment that genuinely failed verification.
    return jsonify({"status": "failed" if error else "settled", "detail": error}), 200


def _return(outcome: str):
    """Shared handler for the three browser redirects."""
    body = {**request.args.to_dict(), **request.form.to_dict()}
    transaction_id = str(body.get("tran_id") or "").strip()

    attempt = PaymentAttempt.query.filter_by(transaction_id=transaction_id).first()
    appointment_id = attempt.appointment_id if attempt else None

    if outcome == "success":
        _, error = _settle(
            str(body.get("val_id") or ""), transaction_id, PaymentAttempt.VIA_REDIRECT
        )
        status = "failed" if error else "paid"
        message = error or ""
    else:
        if attempt and not attempt.is_settled:
            attempt.status = (
                PaymentAttempt.STATUS_CANCELLED
                if outcome == "cancel"
                else PaymentAttempt.STATUS_FAILED
            )
            attempt.failure_reason = (
                "You cancelled the payment." if outcome == "cancel" else "The payment failed."
            )
            if not attempt.appointment.is_paid:
                attempt.appointment.payment_status = Appointment.PAYMENT_UNPAID
            db.session.commit()
        status = outcome
        message = ""

    query = f"?status={status}&appointment={appointment_id or ''}"
    if message:
        query += f"&message={request.args.get('_', '') or message}"
    return redirect(_frontend(f"payment-return.html{query}"))


@payments_bp.route("/return/success", methods=["GET", "POST"])
def return_success():
    return _return("success")


@payments_bp.route("/return/fail", methods=["GET", "POST"])
def return_fail():
    return _return("fail")


@payments_bp.route("/return/cancel", methods=["GET", "POST"])
def return_cancel():
    return _return("cancel")


@payments_bp.get("/appointments/<int:appointment_id>/attempts")
@login_required
def list_attempts(appointment_id: int):
    """Payment history for one appointment, for the patient who owns it."""
    user = current_user()
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or (appointment.user_id != user.id and user.role != user.ROLE_ADMIN):
        return jsonify({"error": "Appointment not found"}), 404

    rows = appointment.payment_attempts.order_by(PaymentAttempt.created_at.desc()).all()
    return jsonify([row.to_dict() for row in rows])


@payments_bp.post("/appointments/<int:appointment_id>/refund-request")
@login_required
def request_refund(appointment_id: int):
    """Ask an administrator to cancel and refund a paid appointment.

    No money moves here. Automating a refund would mean a failed refund call
    could leave an appointment cancelled with the patient's money still taken;
    a person decides instead.
    """
    user = current_user()
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.user_id != user.id:
        return jsonify({"error": "Appointment not found"}), 404
    if not appointment.is_paid:
        return jsonify({"error": "This appointment has not been paid for."}), 400
    if appointment.is_cancelled:
        return jsonify({"error": "This appointment is already cancelled."}), 400

    reason = " ".join(str((request.get_json(silent=True) or {}).get("reason") or "").split())
    if not reason:
        return jsonify({"error": "Please say why you need to cancel."}), 400

    appointment.refund_requested_at = datetime.now(UTC)
    appointment.refund_reason = reason[:300]
    db.session.commit()
    return jsonify(appointment.to_dict())
