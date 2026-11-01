# CareSphere implementation report

## Scope
Implemented the Prescription OCR persistence workflow, medication reminder plans and dose tracking, and the in-app notification inbox within the existing Flask + vanilla JavaScript architecture.

## Files created
- `backend/app/models/prescription.py`
- `backend/app/models/reminder.py`
- `backend/app/models/notification.py`
- `backend/app/blueprints/prescriptions/__init__.py`
- `backend/app/blueprints/prescriptions/routes.py`
- `backend/app/blueprints/reminders/__init__.py`
- `backend/app/blueprints/reminders/routes.py`
- `backend/app/blueprints/notifications/__init__.py`
- `backend/app/blueprints/notifications/routes.py`
- `backend/migrations/versions/1a2b3c4d5e6f_prescriptions_reminders_notifications.py`
- `frontend/medications.html`
- `frontend/notifications.html`
- `frontend/assets/js/pages/medications.js`
- `frontend/assets/js/pages/notifications.js`
- `backend/tests/test_prescriptions_reminders_notifications.py`

## Files modified
- `README.md`
- `backend/app/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/blueprints/payments/routes.py`
- `frontend/ocr.html`
- `frontend/assets/js/pages/ocr.js`
- `frontend/assets/js/ui/nav.js`\n- `frontend/assets/js/icons.js`

## Features implemented
### Prescription OCR
- Preserved existing browser-side Tesseract OCR, image validation, drag/drop, paste, preview, enhancement, progress, confidence, edit, copy and TXT download.
- Added a patient verification form for medicine name, dosage, frequency, duration and instructions.
- Added patient-scoped save/list/delete API. The backend requires at least one manually supplied medicine item and marks the saved record verified only after this explicit submit.
- Emits an in-app notification after a prescription is saved.

### Medication reminders
- Manual medication plans with dosage, frequency, one or more daily times, start/end dates and instructions.
- Optional association with a verified prescription owned by the same patient.
- Edit fields/active state, pause/activate, and delete plan APIs with dashboard controls.\n- Start a plan from a verified prescription, with its first medicine item prefilled for patient review.
- Today's schedule, explicit Taken/Skipped actions, missed-dose tracking, bounded history and adherence percentage.
- Missed doses are created after a 30-minute grace period when the schedule endpoint is queried; a dose is never automatically marked taken.

### Notifications
- Patient-scoped inbox with unread count, mark-one-read, mark-all-read and delete.
- Dedupe keys prevent repeated due/missed/prescription/appointment notification creation.
- Medication due and missed alerts are evaluated when the patient requests today's schedule; the notifications page polls while open.
- Appointment confirmation is created after successful payment settlement.

## Database changes
Migration `1a2b3c4d5e6f` adds:
- `prescriptions`
- `medication_reminders`
- `medication_logs`
- `notifications`

Run `flask --app wsgi db upgrade` from `backend/`.

## New API endpoints
- `GET /api/prescriptions`
- `POST /api/prescriptions`
- `DELETE /api/prescriptions/<id>`
- `GET /api/reminders`
- `POST /api/reminders`
- `PATCH /api/reminders/<id>`
- `DELETE /api/reminders/<id>`
- `GET /api/reminders/today`
- `POST /api/reminders/<id>/log`
- `GET /api/reminders/history`
- `GET /api/notifications`
- `PATCH /api/notifications/<id>/read`
- `POST /api/notifications/read-all`
- `DELETE /api/notifications/<id>`

All new API routes require an authenticated patient and filter records by the current database-backed user ID.

## Tests and static checks
- Added backend tests for patient verification, data isolation, reminder logging, and notification read status.
- `node --check` executed for all frontend JavaScript files: passed (20 files).
- Python AST syntax parsing executed for all 74 backend Python files: passed.
- `pytest -q` attempted, but could not start because Flask is not installed in the provided execution environment (`ModuleNotFoundError: No module named 'flask'`). Therefore the backend test suite and API/database integration tests are **not verified as passing** in this environment.
- `ruff`, npm lint/format checks, and browser end-to-end tests were not run because their dependencies/browser automation are not installed in this environment. Installing Python requirements was attempted but the environment had no network access. Database migrations and API integration tests consequently remain unverified.

## Known limitations / manual configuration
- Run the documented backend dependency installation and database migration before using these APIs.
- OCR engine still loads Tesseract.js from its existing CDN at runtime; network access is needed for the first engine download.
- Web Notifications work only while the CareSphere notifications page is open and polling. No service worker/Web Push provider or server-side scheduler is configured, so closed-browser/background delivery is not supported.
- Appointment notifications are created on successful payment confirmation. Appointment reminders ahead of the appointment time are not yet scheduled.
- The OCR review UI currently saves one manually verified medicine item per prescription submission; the backend data model supports multiple items.
- The frontend uses the existing session-cookie API and assumes the documented local frontend/backend origins.
