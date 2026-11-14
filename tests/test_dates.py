from datetime import date, datetime

import pytest

from exam_agent.dates import PARIS, exam_times, resolve_date


# --- Absolute dates -------------------------------------------------------------


def test_day_and_month_take_the_email_year():
    # e1: email of 2026-05-04, "le jeudi 28 mai"
    assert resolve_date(date(2026, 5, 4), day=28, month=5, weekday="thursday") == date(2026, 5, 28)


def test_explicit_year_is_used():
    # e2: "Le Jeudi 7 Mai 2026"
    assert resolve_date(date(2026, 4, 8), day=7, month=5, year=2026, weekday="thursday") == date(2026, 5, 7)


def test_month_already_passed_means_next_year():
    # A November email announcing "le 15 janvier"
    assert resolve_date(date(2026, 11, 20), day=15, month=1) == date(2027, 1, 15)


def test_same_day_as_email_stays_in_this_year():
    # e4 subject: "examen du jeudi 12 mars", sent on 12 March
    assert resolve_date(date(2026, 3, 12), day=12, month=3) == date(2026, 3, 12)


def test_wrong_weekday_is_rejected():
    with pytest.raises(ValueError, match="is a thursday, but the email says friday"):
        resolve_date(date(2026, 5, 4), day=28, month=5, weekday="friday")


def test_impossible_date_is_rejected():
    with pytest.raises(ValueError, match="not a real date"):
        resolve_date(date(2026, 1, 10), day=31, month=2)


def test_missing_day_is_rejected():
    with pytest.raises(ValueError):
        resolve_date(date(2026, 1, 10), month=2)


# --- Relative dates --------------------------------------------------------------


def test_ce_soir_is_the_email_day():
    # e4: "ce soir à 18h15", email of Thursday 2026-03-12
    assert resolve_date(date(2026, 3, 12), relative="today") == date(2026, 3, 12)


def test_demain():
    assert resolve_date(date(2026, 3, 12), relative="tomorrow") == date(2026, 3, 13)


def test_ce_jeudi_from_a_tuesday():
    # e3: email of Tuesday 2026-03-24, "ce jeudi"
    assert resolve_date(date(2026, 3, 24), relative="this", weekday="thursday") == date(2026, 3, 26)


def test_ce_jeudi_sent_on_a_thursday_is_that_day():
    assert resolve_date(date(2026, 3, 26), relative="this", weekday="thursday") == date(2026, 3, 26)


def test_ce_lundi_sent_on_a_friday_is_the_coming_monday():
    assert resolve_date(date(2026, 3, 27), relative="this", weekday="monday") == date(2026, 3, 30)


def test_next_week():
    # Tuesday 2026-04-07: "mercredi de la semaine prochaine"
    assert resolve_date(date(2026, 4, 7), relative="next_week", weekday="wednesday") == date(2026, 4, 15)


def test_relative_weekday_without_weekday_is_rejected():
    with pytest.raises(ValueError, match="needs a weekday"):
        resolve_date(date(2026, 3, 24), relative="this")


# --- Times -----------------------------------------------------------------------


def test_start_and_end_from_email():
    # e1: "de 16h30 à 18h30"
    start, end = exam_times(date(2026, 5, 28), "16:30", "18:30")
    assert start == datetime(2026, 5, 28, 16, 30, tzinfo=PARIS)
    assert end == datetime(2026, 5, 28, 18, 30, tzinfo=PARIS)


def test_missing_end_defaults_to_two_hours():
    # e4: "à 18h15", no length
    _, end = exam_times(date(2026, 3, 12), "18:15")
    assert end == datetime(2026, 3, 12, 20, 15, tzinfo=PARIS)


def test_end_before_start_is_rejected():
    with pytest.raises(ValueError, match="not after start"):
        exam_times(date(2026, 3, 12), "18:15", "16:00")


def test_badly_written_time_is_rejected():
    with pytest.raises(ValueError, match="must look like"):
        exam_times(date(2026, 3, 12), "18h15")
