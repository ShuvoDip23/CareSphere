"""Payment verification rules.

Pure functions. No network, no database, no Flask - so the rules can be
tested directly with the exact payloads a gateway sends, including the
forged ones.

The prototype's bug lived in one line:

    source = validation or payload

`validation` was only fetched when the request happened to carry a `val_id`.
Omit it and `source` fell back to `payload` - the raw query string - so the
status, amount, transaction id and currency were all checked against values
the caller had just supplied. Hitting

    /api/payments/success?tran_id=CL6-...&status=VALID&amount=2000&currency=BDT

marked the appointment paid without any money moving. I reproduced it against
a copy of the old database before writing this.

The fix is not a better comparison. It is that an unvalidated payload is never
evidence of anything: `verify()` takes the gateway's own validation response
as a separate argument and refuses outright when it is missing.
"""

from decimal import Decimal, InvalidOperation

#: SSLCommerz reports a settled transaction as VALID, or VALIDATED when the
#: validation call is replayed for one it has already settled.
SETTLED_STATUSES = frozenset({"VALID", "VALIDATED"})
CURRENCY = "BDT"

#: How long an unpaid appointment keeps its slot. Long enough to finish a card
#: payment or retry once; short enough that an abandoned checkout does not
#: block a consulting slot for the rest of the day.
HOLD_MINUTES = 30


class Rejected(Exception):
    """Carries the reason a payment was not accepted.

    A string rather than a code: every one of these is written into the
    payment attempt row and read later by a human working out what happened.
    """


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def amounts_match(expected, received) -> bool:
    """Compare money as decimals, never as floats or strings.

    `"1500"`, `"1500.00"` and `1500.0` are the same payment; `0.1 + 0.2` is
    not `0.3`.
    """
    left, right = _decimal(expected), _decimal(received)
    return left is not None and right is not None and left == right


def is_settled(status) -> bool:
    return str(status or "").strip().upper() in SETTLED_STATUSES


def verify(validation: dict | None, *, expected_amount, expected_tran_id: str) -> dict:
    """Accept a payment, or raise Rejected with the reason.

    `validation` is the parsed body of the gateway's own validation API call -
    fetched server-to-server, keyed by the merchant password, and never
    supplied by the browser. The callback query string is deliberately not a
    parameter: there is nothing in it this function is allowed to trust.

    Returns the fields worth keeping on the attempt.
    """
    if not validation:
        # The whole bug, in one guard. No validation response means the
        # payment is unproven, whatever the browser claims.
        raise Rejected("The payment could not be verified with SSLCommerz.")

    status = validation.get("status")
    if not is_settled(status):
        raise Rejected(f"SSLCommerz reported this transaction as {status or 'unknown'}.")

    tran_id = str(validation.get("tran_id") or "").strip()
    if not tran_id or tran_id != expected_tran_id:
        # Without this, a settled payment for appointment A could be presented
        # as payment for the more expensive appointment B.
        raise Rejected("This transaction belongs to a different appointment.")

    # `currency_amount` is the amount in the store's own currency; `amount`
    # can be the converted figure when the card was charged in another.
    amount = validation.get("currency_amount", validation.get("amount"))
    if not amounts_match(expected_amount, amount):
        raise Rejected("The amount paid does not match the consultation fee.")

    currency = str(validation.get("currency_type") or validation.get("currency") or "").upper()
    if currency != CURRENCY:
        raise Rejected(f"Payment was made in {currency or 'an unknown currency'}, not {CURRENCY}.")

    return {
        "val_id": str(validation.get("val_id") or "") or None,
        "tran_id": tran_id,
        "amount": str(_decimal(amount)),
        "card_type": validation.get("card_type") or validation.get("card_issuer"),
        "bank_tran_id": validation.get("bank_tran_id"),
    }


def build_transaction_id(appointment_id: int, token: str) -> str:
    """`CS-42-9f3c1a...` - readable, and unique per attempt.

    Per attempt, not per appointment: the prototype reused one id across
    retries, so a second attempt could be settled against the first attempt's
    validation record.
    """
    return f"CS-{appointment_id}-{token}"


def appointment_id_from(transaction_id: str) -> int | None:
    """Recover the appointment from a transaction id, without trusting it.

    Used only to find the row; everything about that row is then checked
    against the gateway's own validation response.
    """
    parts = str(transaction_id or "").split("-")
    if len(parts) < 3 or parts[0] != "CS":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None
