"""Deduplicated notifications must never fail the thing that triggered them.

`Notification.dedupe_key` is UNIQUE, which is the right way to make "notify
once" a guarantee. But a UNIQUE constraint raises on a duplicate, and all
three callers sit inside something that matters more than the message: a
settled payment, a saved prescription, a loaded medication schedule.

Every test here fails without `Notification.enqueue`.
"""

import time
from datetime import UTC, date, datetime, timedelta

import pytest

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import Doctor, DoctorAvailability, Specialty
from app.models.notification import Notification
from app.models.payment import PaymentAttempt
from app.models.reminder import MedicationReminder
from app.models.user import User
from app.services import sslcommerz

FEE = 1500


@pytest.fixture
def signed_in(client, patient):
    client.post("/api/login", json={"email": patient.email, "password": "correct-horse"})
    return patient


# ===========================================================================
# The helper itself
# ===========================================================================


def test_a_duplicate_key_is_skipped_rather_than_raised(app, patient):
    first = Notification.enqueue(
        patient.id, kind="test", title="One", message="m", dedupe_key="same"
    )
    db.session.commit()

    second = Notification.enqueue(
        patient.id, kind="test", title="Two", message="m", dedupe_key="same"
    )
    db.session.commit()

    assert first is not None
    assert second is None
    assert Notification.query.filter_by(dedupe_key="same").count() == 1


def test_a_skipped_duplicate_leaves_the_transaction_usable(app, patient):
    """The savepoint is the point. Without it the failed insert poisons the
    session and the caller's own commit dies with it."""
    Notification.enqueue(patient.id, kind="test", title="One", message="m", dedupe_key="same")
    db.session.commit()

    Notification.enqueue(patient.id, kind="test", title="Two", message="m", dedupe_key="same")

    # The surrounding work must still commit.
    patient.name = "Renamed After A Duplicate"
    db.session.commit()
    assert db.session.get(User, patient.id).name == "Renamed After A Duplicate"


def test_notifications_without_a_dedupe_key_are_never_merged(app, patient):
    for index in range(3):
        Notification.enqueue(patient.id, kind="test", title=f"#{index}", message="m")
    db.session.commit()
    assert Notification.query.count() == 3


# ===========================================================================
# Bug 1 — a second settlement on one appointment crashed the payment
# ===========================================================================


@pytest.fixture
def paid_twice_setup(app, patient):
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
    db.session.add(
        DoctorAvailability(doctor_id=doctor.id, day_of_week=0, start_time="09:00", end_time="12:00")
    )

    when = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3)
    appointment = Appointment(
        user_id=patient.id,
        doctor_id=doctor.id,
        scheduled_for=when,
        slot_key=Appointment.build_slot_key(when),
        reason="Chest discomfort",
        fee_at_booking=FEE,
    )
    db.session.add(appointment)
    db.session.flush()

    # Two attempts, exactly as a retry produces.
    for token in ("aaaaaa", "bbbbbb"):
        db.session.add(
            PaymentAttempt(
                appointment_id=appointment.id,
                transaction_id=f"CS-{appointment.id}-{token}",
                amount=FEE,
            )
        )
    db.session.commit()
    return appointment


def _settled(tran_id):
    return {
        "status": "VALID",
        "tran_id": tran_id,
        "val_id": f"val-{tran_id}",
        "currency_amount": f"{FEE}.00",
        "currency_type": "BDT",
        "card_type": "VISA-Dutch Bangla",
        "bank_tran_id": "B1",
    }


def test_a_second_settlement_does_not_crash_the_payment(app, paid_twice_setup, monkeypatch):
    """Two checkout sessions on one appointment: the UI offers retry, so this
    is reachable. The second settlement used to raise IntegrityError *after*
    the money had been taken."""
    from app.blueprints.payments.routes import _settle

    monkeypatch.setattr(sslcommerz, "validate", lambda val_id: _settled(val_id[4:]))
    appointment = paid_twice_setup

    _, first_error = _settle(
        f"val-CS-{appointment.id}-aaaaaa", f"CS-{appointment.id}-aaaaaa", "ipn"
    )
    _, second_error = _settle(
        f"val-CS-{appointment.id}-bbbbbb", f"CS-{appointment.id}-bbbbbb", "redirect"
    )

    assert first_error is None
    assert second_error is None
    assert db.session.get(Appointment, appointment.id).payment_status == (Appointment.PAYMENT_PAID)
    # One appointment, one confirmation — that is what dedupe_key is for.
    assert (
        Notification.query.filter_by(dedupe_key=f"appointment-confirmed:{appointment.id}").count()
        == 1
    )


# ===========================================================================
# Bug 2 — the medication schedule crashed on its second load
# ===========================================================================


def test_the_medication_schedule_survives_a_refresh(client, signed_in):
    """A dose that is due but not yet logged re-enters the same branch on
    every load, because no log is written for it. Refreshing the medications
    page within 30 minutes of a dose used to return a 500."""
    due = (datetime.now() - timedelta(minutes=5)).strftime("%H:%M")
    db.session.add(
        MedicationReminder(
            patient_id=signed_in.id,
            medicine_name="Napa",
            dosage="500mg",
            frequency="1+0+1",
            times=[due],
            start_date=date.today(),
            active=True,
        )
    )
    db.session.commit()

    assert client.get("/api/reminders/today").status_code == 200
    assert client.get("/api/reminders/today").status_code == 200
    assert client.get("/api/reminders/today").status_code == 200

    assert Notification.query.filter_by(kind="medication_reminder").count() == 1


def test_a_missed_dose_is_announced_once(client, signed_in):
    missed = (datetime.now() - timedelta(minutes=45)).strftime("%H:%M")
    db.session.add(
        MedicationReminder(
            patient_id=signed_in.id,
            medicine_name="Seclo",
            dosage="20mg",
            frequency="1+0+0",
            times=[missed],
            start_date=date.today(),
            active=True,
        )
    )
    db.session.commit()

    client.get("/api/reminders/today")
    client.get("/api/reminders/today")
    assert Notification.query.filter_by(kind="missed_medication").count() == 1


# ===========================================================================
# Bug 3 — doctors could be given notifications they could not read
# ===========================================================================


def test_a_doctor_can_read_their_own_notifications(client, app):
    """Booking only needs a login, so a doctor can book and pay — and then be
    sent a confirmation. Restricting the inbox to patients made it a 403."""
    user = User(email="doctor@example.com", name="Dr. Reader", role=User.ROLE_DOCTOR)
    user.set_password("correct-horse")
    db.session.add(user)
    db.session.commit()

    db.session.add(
        Notification(
            patient_id=user.id,
            kind="appointment_confirmation",
            title="Appointment confirmed",
            message="Confirmed.",
        )
    )
    db.session.commit()

    client.post("/api/login", json={"email": user.email, "password": "correct-horse"})
    response = client.get("/api/notifications")
    assert response.status_code == 200
    assert response.get_json()["unread_count"] == 1


def test_the_inbox_is_still_scoped_to_the_signed_in_user(client, signed_in, app):
    other = User(email="someone.else@example.com", name="Other")
    other.set_password("correct-horse")
    db.session.add(other)
    db.session.commit()

    db.session.add(
        Notification(patient_id=other.id, kind="test", title="Theirs", message="private")
    )
    db.session.commit()

    body = client.get("/api/notifications").get_json()
    assert body["notifications"] == []
    assert body["unread_count"] == 0


@pytest.fixture
def dhaka_timezone(monkeypatch):
    """Run a test in Asia/Dhaka, and put the process back afterwards.

    monkeypatch restores the TZ variable on teardown but cannot re-read it -
    only tzset() does that - so without the second call every later test in
    the session keeps running six hours ahead.
    """
    monkeypatch.setenv("TZ", "Asia/Dhaka")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.skipif(
    not hasattr(time, "tzset"), reason="TZ cannot be changed at runtime on this platform"
)
def test_marking_read_stores_utc_not_local_time(client, signed_in, dhaka_timezone):
    """`datetime.now()` stored naive local time into a column holding UTC.

    On a UTC machine the two are identical, so the test runs under Asia/Dhaka
    - the timezone this project is actually used in - where the bug is six
    hours wide. CI is Linux, so this always runs there.
    """
    row = Notification(patient_id=signed_in.id, kind="test", title="T", message="m")
    db.session.add(row)
    db.session.commit()

    assert client.patch(f"/api/notifications/{row.id}/read").status_code == 200
    stored = db.session.get(Notification, row.id).read_at

    # The column is naive, so compare against naive UTC.
    drift = abs((stored - datetime.now(UTC).replace(tzinfo=None)).total_seconds())
    assert drift < 120, f"read_at is {drift:.0f}s from UTC - local time was stored"
