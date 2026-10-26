"""Payment endpoints end to end, with SSLCommerz replaced.

`sslcommerz.validate` is the only thing patched. Everything else - the
routes, the verification rules, the appointment transitions - runs for real,
so what these tests exercise is the code that will run in production.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import Doctor, DoctorAvailability, Specialty
from app.models.payment import PaymentAttempt
from app.models.user import User
from app.services import payments, sslcommerz

FEE = 1500


@pytest.fixture
def clinic(app, patient):
    specialty = Specialty.get_or_create("Cardiologist")
    db.session.flush()
    doctor = Doctor(
        name="Dr. Anwar Hossain",
        specialty=specialty,
        hospital="Padma Heart Centre",
        location="Laxmipur, Rajshahi",
        phone="+8801711000101",
        fee=FEE,
        approval_status=Doctor.STATUS_APPROVED,
    )
    db.session.add(doctor)
    db.session.flush()
    for day in range(7):
        db.session.add(
            DoctorAvailability(
                doctor_id=doctor.id, day_of_week=day, start_time="09:00", end_time="12:00"
            )
        )

    when = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3, hours=1)
    appointment = Appointment(
        user_id=patient.id,
        doctor_id=doctor.id,
        scheduled_for=when,
        slot_key=Appointment.build_slot_key(when),
        reason="Chest discomfort when walking",
        fee_at_booking=FEE,
    )
    db.session.add(appointment)
    db.session.commit()
    return {"doctor": doctor, "appointment": appointment, "patient": patient}


@pytest.fixture
def configured(app):
    app.config["SSLCOMMERZ_STORE_ID"] = "testbox"
    app.config["SSLCOMMERZ_STORE_PASSWORD"] = "testbox@ssl"
    app.config["PUBLIC_BASE_URL"] = "http://127.0.0.1:5000"
    return app


@pytest.fixture
def signed_in(client, clinic):
    client.post("/api/login", json={"email": clinic["patient"].email, "password": "correct-horse"})
    return clinic


@pytest.fixture
def opened(client, signed_in, configured, monkeypatch):
    """An appointment with a checkout session already opened."""
    monkeypatch.setattr(
        sslcommerz,
        "start_session",
        lambda **kwargs: {"gateway_url": "https://sandbox.example/pay/abc", "session_key": "sk1"},
    )
    response = client.post(f"/api/payments/appointments/{signed_in['appointment'].id}/session")
    assert response.status_code == 201
    return {**signed_in, "transaction_id": response.get_json()["transaction_id"]}


def settled(tran_id, amount=f"{FEE}.00", **overrides):
    return {
        "status": "VALID",
        "tran_id": tran_id,
        "val_id": "2410241530abcd",
        "currency_amount": amount,
        "currency_type": "BDT",
        "card_type": "VISA-Dutch Bangla",
        "bank_tran_id": "241024153012ABC",
        **overrides,
    }


# ===========================================================================
# The CareLink forgery, replayed against this code
# ===========================================================================


def test_the_prototype_forgery_does_not_mark_an_appointment_paid(client, opened, monkeypatch):
    """The original attack, verbatim in shape.

    In CareLink, hitting the success callback with hand-written query
    parameters and no `val_id` flipped an appointment to paid, because the
    handler fell back to `source = validation or payload`. Here the missing
    `val_id` means there is nothing to validate, so nothing is believed.

    Every forged field is deliberately *correct* - the right transaction id,
    the exact fee, the right currency. If any of them were wrong, a later
    check would reject the request and this test would pass even with the
    original bug restored, proving nothing.
    """
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: None)

    response = client.get(
        "/api/payments/return/success",
        query_string={
            "tran_id": opened["transaction_id"],
            "status": "VALID",
            "currency_amount": f"{FEE}.00",
            "amount": f"{FEE}.00",
            "currency_type": "BDT",
            "currency": "BDT",
        },
    )
    assert response.status_code == 302
    assert "status=failed" in response.headers["Location"]

    appointment = db.session.get(Appointment, opened["appointment"].id)
    assert appointment.payment_status != Appointment.PAYMENT_PAID
    assert appointment.status != Appointment.STATUS_CONFIRMED


def test_the_forged_ipn_is_refused_too(client, opened, monkeypatch):
    """IPN is unauthenticated by nature, so it believes nothing either."""
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: None)

    response = client.post(
        "/api/payments/ipn",
        data={
            "tran_id": opened["transaction_id"],
            "status": "VALID",
            "currency_amount": f"{FEE}.00",
            "currency_type": "BDT",
        },
    )
    assert response.get_json()["status"] == "failed"
    assert db.session.get(Appointment, opened["appointment"].id).payment_status != (
        Appointment.PAYMENT_PAID
    )


def test_a_gateway_that_says_the_payment_failed_is_believed(client, opened, monkeypatch):
    monkeypatch.setattr(
        sslcommerz,
        "validate",
        lambda val_id: settled(opened["transaction_id"], status="FAILED"),
    )
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    assert db.session.get(Appointment, opened["appointment"].id).payment_status == (
        Appointment.PAYMENT_FAILED
    )


def test_paying_less_than_the_fee_is_refused(client, opened, monkeypatch):
    monkeypatch.setattr(
        sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"], amount="900.00")
    )
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    attempt = PaymentAttempt.query.one()
    assert attempt.status == PaymentAttempt.STATUS_FAILED
    assert "amount" in attempt.failure_reason.lower()


def test_a_validation_for_another_transaction_is_refused(client, opened, monkeypatch):
    """A settled cheap payment must not confirm an expensive appointment."""
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled("CS-999-deadbeef"))
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    assert db.session.get(Appointment, opened["appointment"].id).payment_status != (
        Appointment.PAYMENT_PAID
    )


def test_the_fee_is_read_from_the_booking_not_the_doctors_current_price(
    client, opened, monkeypatch
):
    """An admin editing the fee mid-payment broke every in-flight payment in
    the prototype, because validation compared against doctor.fee."""
    opened["doctor"].fee = 5000
    db.session.commit()

    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"]))
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    assert db.session.get(Appointment, opened["appointment"].id).payment_status == (
        Appointment.PAYMENT_PAID
    )


# ===========================================================================
# The happy path and its edges
# ===========================================================================


def test_a_settled_payment_confirms_the_appointment(client, opened, monkeypatch):
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"]))
    response = client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    assert "status=paid" in response.headers["Location"]

    appointment = db.session.get(Appointment, opened["appointment"].id)
    assert appointment.payment_status == Appointment.PAYMENT_PAID
    assert appointment.status == Appointment.STATUS_CONFIRMED
    assert appointment.payment_method == "VISA-Dutch Bangla"

    attempt = PaymentAttempt.query.one()
    assert attempt.status == PaymentAttempt.STATUS_PAID
    assert attempt.settled_via == PaymentAttempt.VIA_REDIRECT


def test_ipn_and_the_redirect_both_arriving_settles_once(client, opened, monkeypatch):
    """Both channels fire for the same payment. The second must change
    nothing, including not settling it a second time."""
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"]))

    client.post("/api/payments/ipn", data={"tran_id": opened["transaction_id"], "val_id": "v1"})
    first = PaymentAttempt.query.one()
    assert first.settled_via == PaymentAttempt.VIA_IPN
    settled_at = first.settled_at

    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    again = PaymentAttempt.query.one()
    assert again.settled_via == PaymentAttempt.VIA_IPN
    assert again.settled_at == settled_at


def test_a_gateway_outage_leaves_the_attempt_open_to_retry(client, opened, monkeypatch):
    """Not reaching SSLCommerz is not the same as the payment failing."""

    def boom(val_id):
        raise sslcommerz.GatewayError("SSLCommerz could not be reached.")

    monkeypatch.setattr(sslcommerz, "validate", boom)
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    assert PaymentAttempt.query.one().status == PaymentAttempt.STATUS_INITIATED


def test_cancelling_at_the_gateway_leaves_the_appointment_payable(client, opened):
    client.get("/api/payments/return/cancel", query_string={"tran_id": opened["transaction_id"]})
    appointment = db.session.get(Appointment, opened["appointment"].id)
    assert appointment.payment_status == Appointment.PAYMENT_UNPAID
    assert appointment.can_pay is True
    assert PaymentAttempt.query.one().status == PaymentAttempt.STATUS_CANCELLED


def test_each_attempt_gets_a_new_transaction_id(client, opened, monkeypatch, configured):
    monkeypatch.setattr(
        sslcommerz,
        "start_session",
        lambda **kwargs: {"gateway_url": "https://sandbox.example/pay/2", "session_key": "sk2"},
    )
    second = client.post(f"/api/payments/appointments/{opened['appointment'].id}/session")
    assert second.status_code == 201
    assert second.get_json()["transaction_id"] != opened["transaction_id"]
    assert PaymentAttempt.query.count() == 2


# ===========================================================================
# Access and state
# ===========================================================================


def test_opening_a_session_requires_login(client, clinic):
    assert (
        client.post(f"/api/payments/appointments/{clinic['appointment'].id}/session").status_code
        == 401
    )


def test_you_cannot_pay_for_someone_elses_appointment(client, clinic, configured):
    other = User(email="intruder@example.com", name="Intruder")
    other.set_password("correct-horse")
    db.session.add(other)
    db.session.commit()

    client.post("/api/login", json={"email": other.email, "password": "correct-horse"})
    response = client.post(f"/api/payments/appointments/{clinic['appointment'].id}/session")
    assert response.status_code == 404


def test_an_already_paid_appointment_cannot_open_a_new_session(client, opened, configured):
    opened["appointment"].payment_status = Appointment.PAYMENT_PAID
    db.session.commit()
    assert (
        client.post(f"/api/payments/appointments/{opened['appointment'].id}/session").status_code
        == 409
    )


def test_payment_is_refused_when_the_gateway_is_not_configured(client, signed_in, app):
    app.config["SSLCOMMERZ_STORE_ID"] = None
    app.config["SSLCOMMERZ_STORE_PASSWORD"] = None
    response = client.post(f"/api/payments/appointments/{signed_in['appointment'].id}/session")
    assert response.status_code == 503


def test_an_unknown_transaction_is_not_found(client, configured):
    assert client.post("/api/payments/ipn", data={"tran_id": "CS-1-nope"}).status_code == 404


# ===========================================================================
# The 30-minute hold
# ===========================================================================


def test_an_abandoned_booking_releases_its_slot(client, clinic, app):
    from app.blueprints.payments.routes import release_expired_holds

    appointment = clinic["appointment"]
    appointment.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        minutes=payments.HOLD_MINUTES + 1
    )
    db.session.commit()

    assert release_expired_holds() == 1
    refreshed = db.session.get(Appointment, appointment.id)
    assert refreshed.slot_key is None
    assert refreshed.status == Appointment.STATUS_CANCELLED


def test_a_recent_booking_keeps_its_slot(client, clinic, app):
    from app.blueprints.payments.routes import release_expired_holds

    assert release_expired_holds() == 0
    assert db.session.get(Appointment, clinic["appointment"].id).slot_key is not None


def test_a_paid_booking_is_never_released(client, opened, monkeypatch, app):
    from app.blueprints.payments.routes import release_expired_holds

    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"]))
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    opened["appointment"].created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db.session.commit()

    assert release_expired_holds() == 0
    assert db.session.get(Appointment, opened["appointment"].id).slot_key is not None


def test_a_released_slot_cannot_be_paid_for(client, opened, configured):
    opened["appointment"].release_slot()
    db.session.commit()
    response = client.post(f"/api/payments/appointments/{opened['appointment'].id}/session")
    assert response.status_code == 409
    assert "released" in response.get_json()["error"]


# ===========================================================================
# Refund requests
# ===========================================================================


@pytest.fixture
def paid(client, opened, monkeypatch):
    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: settled(opened["transaction_id"]))
    client.get(
        "/api/payments/return/success",
        query_string={"tran_id": opened["transaction_id"], "val_id": "v1"},
    )
    return opened


def test_a_paid_appointment_can_request_a_refund(client, paid):
    response = client.post(
        f"/api/payments/appointments/{paid['appointment'].id}/refund-request",
        json={"reason": "I have to travel that week."},
    )
    assert response.status_code == 200
    assert response.get_json()["refund_requested"] is True


def test_a_refund_request_needs_a_reason(client, paid):
    assert (
        client.post(
            f"/api/payments/appointments/{paid['appointment'].id}/refund-request",
            json={"reason": "   "},
        ).status_code
        == 400
    )


def test_an_unpaid_appointment_cannot_request_a_refund(client, opened):
    assert (
        client.post(
            f"/api/payments/appointments/{opened['appointment'].id}/refund-request",
            json={"reason": "Changed my mind"},
        ).status_code
        == 400
    )


def test_requesting_a_refund_does_not_move_any_money(client, paid):
    """Nothing is automated here on purpose: a failed refund call would leave
    the appointment cancelled with the patient's money still taken."""
    client.post(
        f"/api/payments/appointments/{paid['appointment'].id}/refund-request",
        json={"reason": "Travelling"},
    )
    appointment = db.session.get(Appointment, paid["appointment"].id)
    assert appointment.payment_status == Appointment.PAYMENT_PAID
    assert appointment.status == Appointment.STATUS_CONFIRMED
    assert PaymentAttempt.query.one().status == PaymentAttempt.STATUS_PAID


def test_the_payment_history_is_private_to_its_owner(client, paid):
    other = User(email="nosy@example.com", name="Nosy")
    other.set_password("correct-horse")
    db.session.add(other)
    db.session.commit()

    client.post("/api/logout")
    client.post("/api/login", json={"email": other.email, "password": "correct-horse"})
    assert (
        client.get(f"/api/payments/appointments/{paid['appointment'].id}/attempts").status_code
        == 404
    )
