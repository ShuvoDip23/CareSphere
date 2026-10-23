"""Appointment slot arithmetic.

Pure functions: no Flask, no database, no clock of their own. Every caller
passes the values it already holds, which is what makes the awkward cases -
a window that does not divide evenly, a booking on today's date, the last
slot before closing - testable without a request or a fixture.

The prototype derived slots inside the request handler and, when a day had no
rows yet, inserted fifty-six availability rows from a GET. Separating the
arithmetic from the storage is what removes that whole category of problem.
"""

from datetime import UTC, date, datetime, time, timedelta

#: How far ahead a patient may book. Beyond this a doctor's weekly window is
#: not a reliable promise - leave or a schedule change is likelier than not.
DEFAULT_HORIZON_DAYS = 60

MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 240


def parse_date(value: str) -> date | None:
    """`"2026-11-03"` -> date, or None. Never raises."""
    try:
        return datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_time(value: str) -> time | None:
    """`"09:30"` -> time, or None. Never raises.

    Rejects `"9:30"` deliberately: the stored format is zero-padded, and
    accepting both spellings would let the same slot be written two ways and
    defeat the unique constraint on (doctor, scheduled_for).
    """
    text = str(value or "").strip()
    if len(text) != 5 or text[2] != ":":
        return None
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None


def today_utc() -> date:
    return datetime.now(UTC).date()


def window_slot_times(start_time: str, end_time: str, slot_minutes: int) -> list[str]:
    """Every slot start inside one consulting window.

    The end is exclusive: 09:00-10:00 in 30-minute slots yields 09:00 and
    09:30, not 10:00, because a slot starting at closing time has no room to
    run. A window that does not divide evenly simply stops early - 09:00-10:00
    at 45 minutes yields only 09:00, since 09:45 would overrun.
    """
    start = parse_time(start_time)
    end = parse_time(end_time)
    if start is None or end is None:
        return []
    if not MIN_SLOT_MINUTES <= int(slot_minutes or 0) <= MAX_SLOT_MINUTES:
        return []

    step = timedelta(minutes=int(slot_minutes))
    cursor = datetime.combine(date.min, start)
    closing = datetime.combine(date.min, end)

    times: list[str] = []
    while cursor + step <= closing:
        times.append(cursor.time().strftime("%H:%M"))
        cursor += step
    return times


def slot_times_for_day(windows, day_of_week: int) -> list[str]:
    """Slot starts across every window a doctor consults on that weekday.

    Overlapping windows are deduplicated, so a doctor with 09:00-12:00 and
    11:00-14:00 on the same day offers 11:00 once rather than twice.
    """
    times: set[str] = set()
    for window in windows:
        if window.day_of_week % 7 != day_of_week % 7:
            continue
        times.update(window_slot_times(window.start_time, window.end_time, window.slot_minutes))
    return sorted(times)


def bookable_reason(on: date, now: date, horizon_days: int = DEFAULT_HORIZON_DAYS) -> str | None:
    """None when the date may be booked, otherwise why it may not.

    Today is allowed. The prototype rejected nothing at all, so a patient
    could book an appointment into last month and it would sit in the list
    looking perfectly valid.
    """
    if on < now:
        return "That date has already passed."
    if on > now + timedelta(days=horizon_days):
        return f"Appointments open {horizon_days} days ahead at most."
    return None


def build_slots(slot_times: list[str], taken: set[str], on: date, now_dt: datetime) -> list[dict]:
    """Annotate each slot start with whether it can still be booked.

    `taken` holds `"HH:MM"` strings already booked for that doctor and date.
    A slot earlier today is reported as past rather than silently dropped, so
    the grid keeps its shape and the patient can see the day is simply
    half gone.
    """
    is_today = on == now_dt.date()
    current = now_dt.time()

    slots = []
    for value in slot_times:
        parsed = parse_time(value)
        is_past = bool(is_today and parsed is not None and parsed <= current)
        is_taken = value in taken
        slots.append(
            {
                "time": value,
                "is_booked": is_taken,
                "is_past": is_past,
                "is_available": not is_taken and not is_past,
            }
        )
    return slots


def combine(on: date, at: time) -> datetime:
    """The naive datetime stored on the appointment row.

    Naive on purpose: clinic hours are wall-clock local time, and storing an
    offset would invite comparing a UTC instant against a doctor's 09:00.
    """
    return datetime.combine(on, at)
