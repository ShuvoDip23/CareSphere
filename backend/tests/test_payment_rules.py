"""The verification rules. No app, no database, no mocks - these are pure.

Several of these replay the exact shapes the CareLink prototype accepted.
"""

import pytest

from app.services.payments import Rejected, amounts_match, build_transaction_id, verify
from app.services.payments import appointment_id_from as appt_id

TRAN = "CS-6-9f3c1a2b"


def validation(**overrides) -> dict:
    """A settled SSLCommerz validation response."""
    return {
        "status": "VALID",
        "tran_id": TRAN,
        "val_id": "2410241530abcd",
        "currency_amount": "1500.00",
        "currency_type": "BDT",
        "card_type": "VISA-Dutch Bangla",
        "bank_tran_id": "241024153012ABC",
        **overrides,
    }


def _verify(validation_body, amount="1500.00", tran_id=TRAN):
    return verify(validation_body, expected_amount=amount, expected_tran_id=tran_id)


# ------------------------------------------------------- the prototype's bug


def test_no_validation_response_is_refused():
    """The whole CareLink forgery, reduced to its root cause.

    The old code read `source = validation or payload`, so when no `val_id`
    was supplied it validated the caller's own query string against itself.
    """
    with pytest.raises(Rejected) as caught:
        _verify(None)
    assert "could not be verified" in str(caught.value)


def test_an_empty_validation_response_is_refused():
    with pytest.raises(Rejected):
        _verify({})


def test_the_forged_callback_payload_is_not_accepted_as_validation():
    """`?tran_id=…&status=VALID&amount=2000&currency=BDT` marked an
    appointment paid in the prototype. Passing that same dict here fails,
    because it carries no val_id and the amount is wrong."""
    forged = {"tran_id": TRAN, "status": "VALID", "amount": "2000", "currency": "BDT"}
    with pytest.raises(Rejected) as caught:
        _verify(forged)
    assert "amount" in str(caught.value).lower()


# --------------------------------------------------------------- acceptance


def test_a_settled_payment_is_accepted():
    result = _verify(validation())
    assert result["tran_id"] == TRAN
    assert result["amount"] == "1500.00"
    assert result["card_type"] == "VISA-Dutch Bangla"


def test_validated_is_accepted_as_well_as_valid():
    """Replaying validation for an already-settled transaction returns
    VALIDATED, which happens whenever IPN and the redirect both arrive."""
    assert _verify(validation(status="VALIDATED"))["tran_id"] == TRAN


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "PENDING", "", None, "UNATTEMPTED"])
def test_anything_but_a_settled_status_is_refused(status):
    with pytest.raises(Rejected):
        _verify(validation(status=status))


@pytest.mark.parametrize("status", ["valid", "VALID ", " Validated"])
def test_case_and_whitespace_in_the_status_are_tolerated(status):
    assert _verify(validation(status=status))["tran_id"] == TRAN


# ----------------------------------------------------------- the four checks


def test_a_transaction_for_another_appointment_is_refused():
    """Otherwise a settled ৳900 payment could be presented against a ৳1,800
    appointment by quoting the wrong transaction id."""
    with pytest.raises(Rejected) as caught:
        _verify(validation(tran_id="CS-9-deadbeef"))
    assert "different appointment" in str(caught.value)


def test_a_short_payment_is_refused():
    with pytest.raises(Rejected) as caught:
        _verify(validation(currency_amount="900.00"))
    assert "does not match" in str(caught.value)


def test_a_foreign_currency_is_refused():
    with pytest.raises(Rejected) as caught:
        _verify(validation(currency_type="USD", currency_amount="1500.00"))
    assert "USD" in str(caught.value)


def test_the_store_currency_amount_wins_over_the_charged_amount():
    """A card charged in USD reports the BDT figure in currency_amount."""
    body = validation(amount="12.50", currency_amount="1500.00")
    assert _verify(body)["amount"] == "1500.00"


# ------------------------------------------------------------ money compare


@pytest.mark.parametrize(
    "expected,received",
    [("1500", "1500.00"), (1500, "1500.0"), ("1500.00", 1500), (1500.0, "1500")],
)
def test_equivalent_amounts_match(expected, received):
    assert amounts_match(expected, received)


@pytest.mark.parametrize("received", ["1499.99", "15000", "", None, "abc", "-1500"])
def test_unequal_or_unparseable_amounts_do_not_match(received):
    assert not amounts_match("1500.00", received)


def test_float_arithmetic_does_not_leak_into_the_comparison():
    """0.1 + 0.2 is 0.30000000000000004 in binary floating point."""
    assert amounts_match(0.1 + 0.2, "0.3")


# -------------------------------------------------------- transaction ids


def test_a_transaction_id_names_its_appointment():
    assert appt_id(build_transaction_id(42, "9f3c1a2b")) == 42


@pytest.mark.parametrize("bad", ["", None, "CS", "CS-x-1", "XX-42-abc", "42"])
def test_an_unreadable_transaction_id_returns_none(bad):
    assert appt_id(bad) is None


def test_each_attempt_gets_its_own_transaction_id():
    """The prototype reused one id across retries, so a second attempt could
    be settled against the first attempt's validation record."""
    assert build_transaction_id(42, "aaa") != build_transaction_id(42, "bbb")
