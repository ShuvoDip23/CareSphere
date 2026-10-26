"""SSLCommerz client.

The only module here that touches the network, so every rule in
`services/payments.py` can be tested without one, and the tests replace one
function to exercise the whole flow offline. CI has no store credentials and
must never make a real call.

Two operations matter:

* `start_session` opens a hosted checkout and returns the URL to send the
  patient to.
* `validate` asks SSLCommerz, server to server and authenticated with the
  store password, what actually happened to a transaction. This is the only
  statement about a payment the application trusts. Nothing arriving through
  the patient's browser is evidence.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app

logger = logging.getLogger(__name__)

SANDBOX_INIT = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
SANDBOX_VALIDATE = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
LIVE_INIT = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
LIVE_VALIDATE = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"

TIMEOUT = 30


class GatewayError(RuntimeError):
    """The gateway could not be reached, or answered with something unusable."""


def _config() -> dict:
    store_id = current_app.config.get("SSLCOMMERZ_STORE_ID")
    store_password = current_app.config.get("SSLCOMMERZ_STORE_PASSWORD")
    if not store_id or not store_password:
        raise GatewayError("Online payment is not configured on this server.")

    sandbox = bool(current_app.config.get("SSLCOMMERZ_SANDBOX", True))
    return {
        "store_id": store_id,
        "store_passwd": store_password,
        "init_url": SANDBOX_INIT if sandbox else LIVE_INIT,
        "validate_url": SANDBOX_VALIDATE if sandbox else LIVE_VALIDATE,
    }


def is_configured() -> bool:
    return bool(
        current_app.config.get("SSLCOMMERZ_STORE_ID")
        and current_app.config.get("SSLCOMMERZ_STORE_PASSWORD")
    )


def _post_form(url: str, fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - fixed https endpoints above
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310  # nosec B310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GatewayError(f"SSLCommerz returned HTTP {exc.code}.") from exc
    except (OSError, ValueError) as exc:
        raise GatewayError("SSLCommerz could not be reached.") from exc


def start_session(*, transaction_id: str, amount, appointment, patient, urls: dict) -> dict:
    """Open a hosted checkout and return {gateway_url, session_key}."""
    config = _config()
    doctor = appointment.doctor

    payload = {
        "store_id": config["store_id"],
        "store_passwd": config["store_passwd"],
        "total_amount": str(amount),
        "currency": "BDT",
        "tran_id": transaction_id,
        "success_url": urls["success"],
        "fail_url": urls["fail"],
        "cancel_url": urls["cancel"],
        "ipn_url": urls["ipn"],
        "cus_name": patient.name,
        "cus_email": patient.email,
        "cus_phone": doctor.phone,
        "cus_add1": doctor.hospital,
        "cus_city": "Rajshahi",
        "cus_country": "Bangladesh",
        "shipping_method": "NO",
        "product_name": f"Consultation with {doctor.name}",
        "product_category": "Healthcare",
        "product_profile": "non-physical-goods",
        # Echoed back on every callback, so a reply can be tied to this
        # attempt even before the transaction id is parsed.
        "value_a": str(appointment.id),
    }

    body = _post_form(config["init_url"], payload)
    if str(body.get("status", "")).upper() != "SUCCESS":
        reason = body.get("failedreason") or "SSLCommerz refused to open a payment session."
        logger.warning("SSLCommerz init failed for %s: %s", transaction_id, reason)
        raise GatewayError(reason)

    url = body.get("GatewayPageURL") or body.get("redirectGatewayURL")
    if not url:
        raise GatewayError("SSLCommerz did not return a payment page.")
    return {"gateway_url": url, "session_key": body.get("sessionkey")}


def validate(val_id: str) -> dict | None:
    """Ask SSLCommerz what happened to a transaction.

    Returns the parsed response, or None when there is nothing to ask about.
    Callers treat None exactly as they treat a failure - `payments.verify`
    refuses both - so a missing `val_id` can never become a settled payment.
    """
    val_id = str(val_id or "").strip()
    if not val_id:
        return None

    config = _config()
    query = urllib.parse.urlencode(
        {
            "val_id": val_id,
            "store_id": config["store_id"],
            "store_passwd": config["store_passwd"],
            "v": 1,
            "format": "json",
        }
    )
    request = urllib.request.Request(  # noqa: S310 - fixed https endpoints above
        f"{config['validate_url']}?{query}"
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310  # nosec B310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GatewayError(f"SSLCommerz validation returned HTTP {exc.code}.") from exc
    except (OSError, ValueError) as exc:
        raise GatewayError("SSLCommerz validation could not be reached.") from exc
