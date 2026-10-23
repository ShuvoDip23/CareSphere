"""Slot arithmetic. No app, no database, no fixtures - these are pure functions."""

from datetime import date, datetime, timedelta

import pytest

from app.services import scheduling


class Window:
    """Stand-in for DoctorAvailability. The service never touches the ORM."""

    def __init__(self, day_of_week, start_time, end_time, slot_minutes=30):
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.slot_minutes = slot_minutes


# --------------------------------------------------------------- parsing


@pytest.mark.parametrize("value", ["", None, "2026-13-01", "03-11-2026", "tomorrow"])
def test_bad_dates_return_none_instead_of_raising(value):
    assert scheduling.parse_date(value) is None


def test_unpadded_time_is_rejected():
    """ "9:30" and "09:30" would be two spellings of one slot.

    The unique constraint compares stored strings, so accepting both would
    let the same slot be booked twice.
    """
    assert scheduling.parse_time("09:30") is not None
    assert scheduling.parse_time("9:30") is None


@pytest.mark.parametrize("value", ["", None, "25:00", "09:60", "09:30:00"])
def test_bad_times_return_none(value):
    assert scheduling.parse_time(value) is None


# ----------------------------------------------------------- slot windows


def test_window_excludes_the_closing_time():
    """A slot starting at closing time has no room to run."""
    assert scheduling.window_slot_times("09:00", "10:00", 30) == ["09:00", "09:30"]


def test_window_that_does_not_divide_evenly_stops_early():
    """09:45 would overrun a 10:00 close, so it is not offered."""
    assert scheduling.window_slot_times("09:00", "10:00", 45) == ["09:00"]


def test_window_shorter_than_one_slot_yields_nothing():
    assert scheduling.window_slot_times("09:00", "09:20", 30) == []


def test_slot_length_outside_sane_bounds_yields_nothing():
    assert scheduling.window_slot_times("09:00", "17:00", 0) == []
    assert scheduling.window_slot_times("09:00", "17:00", 600) == []


def test_overlapping_windows_do_not_duplicate_a_slot():
    windows = [Window(0, "09:00", "12:00"), Window(0, "11:00", "14:00")]
    times = scheduling.slot_times_for_day(windows, 0)
    assert times.count("11:00") == 1
    assert times == sorted(times)


def test_only_the_requested_weekday_is_considered():
    windows = [Window(0, "09:00", "11:00"), Window(3, "15:00", "17:00")]
    assert scheduling.slot_times_for_day(windows, 3) == ["15:00", "15:30", "16:00", "16:30"]
    assert scheduling.slot_times_for_day(windows, 5) == []


# ------------------------------------------------------------- bookability


def test_today_is_bookable():
    today = date(2026, 11, 3)
    assert scheduling.bookable_reason(today, today) is None


def test_yesterday_is_not():
    today = date(2026, 11, 3)
    assert scheduling.bookable_reason(today - timedelta(days=1), today) is not None


def test_beyond_the_horizon_is_not():
    today = date(2026, 11, 3)
    assert scheduling.bookable_reason(today + timedelta(days=61), today, 60) is not None
    assert scheduling.bookable_reason(today + timedelta(days=60), today, 60) is None


# ------------------------------------------------------------ slot marking


def test_booked_and_past_slots_are_marked_but_still_listed():
    """The grid keeps its shape so the patient can see the day is half gone."""
    on = date(2026, 11, 3)
    now = datetime(2026, 11, 3, 9, 45)
    slots = scheduling.build_slots(["09:00", "09:30", "10:00", "10:30"], {"10:30"}, on, now)

    by_time = {slot["time"]: slot for slot in slots}
    assert len(slots) == 4
    # A slot that has already started cannot be booked, even a few minutes in.
    assert by_time["09:00"]["is_past"] is True
    assert by_time["09:30"]["is_past"] is True
    assert by_time["09:00"]["is_available"] is False
    assert by_time["10:30"]["is_booked"] is True
    assert by_time["10:30"]["is_available"] is False
    assert by_time["10:00"]["is_available"] is True


def test_nothing_is_past_on_a_future_date():
    slots = scheduling.build_slots(
        ["09:00"], set(), date(2026, 11, 4), datetime(2026, 11, 3, 23, 0)
    )
    assert slots[0]["is_past"] is False
    assert slots[0]["is_available"] is True
