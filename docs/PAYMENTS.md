# Payments

Appointment fees are taken through SSLCommerz's hosted checkout. No card
details ever reach CareSphere — the patient leaves the site, pays on
SSLCommerz, and comes back.

## The defect this replaces

The CareLink prototype confirmed payments from the success callback's query
string. Its verification did fetch SSLCommerz's validation API, but only when
the request happened to carry a `val_id`, and then:

```python
source = validation or payload
```

Omit `val_id` and `source` became `payload` — the attacker's own query
string. Status, transaction id, amount and currency were then all checked
against values the caller had just supplied. This marked an appointment paid,
with no money moving:

```
/api/payments/success?tran_id=CL6-...&status=VALID&amount=2000&currency=BDT
```

Reproduced against a copy of the prototype's database before any of this was
written.

**The fix is not a stricter comparison.** `services/payments.py` takes the
gateway's validation response as a separate argument and refuses outright
when it is absent. An unvalidated payload is never evidence, so there is no
path through the code where the browser's claims are read as fact.

`tests/test_payments.py` replays that exact attack. Every forged field in it
is deliberately correct — the right transaction id, the exact fee, the right
currency — so that only the missing validation stands between the request and
a confirmed appointment. Restore the old `validation or payload` fallback and
four tests fail.

## How a payment flows

1. `POST /api/payments/appointments/<id>/session` — the patient opens a
   checkout. A new `PaymentAttempt` row is created with a fresh transaction
   id, `CS-<appointment>-<random>`.
2. The patient pays on SSLCommerz.
3. SSLCommerz confirms, by two independent channels:
   - **IPN** → `POST /api/payments/ipn`, server to server. Authoritative:
     it arrives even if the patient closes the tab the moment they pay.
   - **The redirect** → `/api/payments/return/success`, through the
     patient's browser. Convenient, and the only one that works on
     localhost.
4. Both call `_settle`, which ignores what the caller said and asks
   SSLCommerz directly with `val_id`. On success the appointment becomes
   `confirmed` / `paid`.

Both channels routinely fire for the same payment, so `_settle` is
idempotent: the first settles it, the rest find it already paid and change
nothing.

## Running it locally

Put your sandbox credentials in `backend/.env`:

```
SSLCOMMERZ_STORE_ID=yourstore
SSLCOMMERZ_STORE_PASSWORD=yourstore@ssl
SSLCOMMERZ_SANDBOX=true
PUBLIC_BASE_URL=http://127.0.0.1:5000
```

The redirect path works straight away. **IPN cannot reach localhost** —
SSLCommerz is posting from the internet, and `127.0.0.1` means its own
server. To exercise IPN, expose the API through a tunnel and point
`PUBLIC_BASE_URL` at it:

```
ngrok http 5000
PUBLIC_BASE_URL=https://<your-subdomain>.ngrok-free.app
```

Without a tunnel the redirect still confirms the payment, so the flow is
fully demoable; you are just not exercising the channel production relies on.

CI has no credentials and never makes a real call: the tests replace
`sslcommerz.validate`, and everything else runs for real.

## Unpaid slots

An unpaid appointment holds its slot for **30 minutes**
(`payments.HOLD_MINUTES`). After that `release_expired_holds()` clears
`slot_key` and cancels it, which puts the time back on sale. The row stays in
the patient's history.

It runs when someone lists a doctor's slots or tries to book — the moments
the answer matters — rather than from a scheduler, so there is nothing extra
to deploy.

## Refunds

There are none. A paid appointment cannot be cancelled in the app; the
patient sends a request with a reason
(`POST /api/payments/appointments/<id>/refund-request`), it is flagged on the
appointment, and an administrator arranges the refund outside the system.

Automating it was considered and rejected: a refund call that fails partway
leaves an appointment cancelled with the patient's money still taken, and
that is a worse failure than making a person decide.

## What is deliberately not built

- **No card data, ever.** SSLCommerz hosts the form; CareSphere stores only
  the card *type* the gateway reports ("VISA-Dutch Bangla").
- **No partial payments or instalments.**
- **No automated refunds** — see above.
- **No currency other than BDT.** A payment in anything else is rejected
  rather than converted.
