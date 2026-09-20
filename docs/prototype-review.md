# Prototype review

A review of the previous semester's prototype was carried out before starting
the rebuild. It is recorded here because each finding is a requirement on the
corresponding CareSphere module, tracked in `docs/PORTING.md`.

## Critical

**Payment confirmation could be forged.** `/api/payments/success` required no
authentication and, when the gateway did not supply a `val_id`, trusted the
query string it was handed. A request of the form
`?tran_id=<id>&status=VALID&amount=<fee>&currency=BDT` marked an appointment
paid without any money moving. `/api/payments/fail` could likewise alter
another user's appointment. **Requirement:** always call the validation API,
verify the gateway signature and confirm the store ID before changing payment
state.

**Passwords were unsalted SHA-256.** No salt, no work factor. **Requirement:**
Werkzeug PBKDF2. *Fixed in week 1, covered by
`test_password_is_not_stored_as_bare_sha256`.*

**A hard-coded fallback secret key.** `SECRET_KEY` defaulted to a literal in
the source, so session cookies could be forged for any account, including the
administrator. **Requirement:** production refuses to start without a real
secret. *Fixed in week 1.*

**Roles were trusted from the session.** A role change in the database took
effect only after re-login. **Requirement:** resolve the role from the database
on each request. *Fixed in week 1.*

## Functional

- Appointments were committed before the payment session was created, so a
  failed gateway call locked the slot permanently with no expiry.
- `GET /api/doctors/<id>/availability` wrote 56 rows to the database, making an
  unauthenticated read non-idempotent.
- Free-text specialty entry produced both `Cardiologist` and `Cardiology`, so
  filtering by one missed the other.
- Doctor accounts could log in but had no dashboard and could not see their own
  appointments.
- Emergency providers were six fabricated demo records with sequential fake
  phone numbers, presented in the UI as nearby hospitals.
- The emergency PDF, directions and ambulance access promised in proposal §4.7
  were absent.

## Quality

- 2,493 insertions and 2,493 deletions of pure CRLF churn across nine files,
  with no `.gitattributes`.
- `frontend/js/auth.js` (108 lines) was never loaded by any page;
  `frontend/test.html` (254 lines) was a leftover scratch page.
- `escapeHtml`, `getCurrentUser`, `statusClass` and `formatStatusLabel` were
  each defined in two files.
- The Tailwind CDN and a 58KB hand-written stylesheet ran against each other.
- No README, no `.env.example`, no tests.

## What was sound

Output escaping was applied consistently, so there was no XSS surface. Role
injection through the registration body was already blocked. Login errors did
not leak whether an email was registered. The AI assistant's safety design —
disclaimers, emergency rules evaluated independently of the model, and
conservative prompting — is carried forward unchanged.
