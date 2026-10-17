#!/usr/bin/env python3
"""
pop_Hijri_Calendar_anchored.py

Generate Hijri_Calendar for a Gregorian date range using:
  1. Ramadan table as the primary long-range anchor.
  2. Eid_Ul_Fitr table as an independent Shawwal anchor/validation point.
  3. Swiss Ephemeris for astronomical new-moon/crescent estimates.
  4. A constrained fallback system so missing historical transition data
     does not stop the calendar.

IMPORTANT:
- The resulting dates are astronomical/calculated approximations, NOT
  guaranteed historical or future official crescent-sighting dates.
- The Ramadan table and Eid_Ul_Fitr table are treated as project anchors.
- Crescent visibility is only an approximate classifier. It is not a
  replacement for local religious sighting decisions.
- Month lengths are always 29 or 30 days.
- The algorithm prefers astronomical evidence, but anchor constraints win
  whenever necessary to maintain a continuous calendar.
"""

from __future__ import annotations

import itertools
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_DATE = date(1927, 1, 1)
END_DATE = date(2125, 12, 31)

# Project anchor:
# 1445-09-01 Ramadan = 2024-03-11
ANCHOR_HIJRI_YEAR = 1445
ANCHOR_RAMADAN_START = date(2024, 3, 11)

# Visibility policy.
# This is deliberately approximate.
# LIKELY normally produces a 29-day month.
# POSSIBLE and UNLIKELY normally produce 30-day months.
DEFAULT_LENGTH = {
    "LIKELY": 29,
    "POSSIBLE": 30,
    "UNLIKELY": 30,
}

HIJRI_MONTH_NAMES = {
    1: "Muharram",
    2: "Safar",
    3: "Rabi al-Awwal",
    4: "Rabi al-Thani",
    5: "Jumada al-Awwal",
    6: "Jumada al-Thani",
    7: "Rajab",
    8: "Sha'ban",
    9: "Ramadan",
    10: "Shawwal",
    11: "Dhu al-Qi'dah",
    12: "Dhu al-Hijjah",
}


# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class Anchor:
    hijri_year: int
    ramadan_start: date
    ramadan_end: date
    shawwal_start: date
    tabular_eid: date
    ramadan_days: int


@dataclass
class CrescentObservation:
    new_moon_local: datetime
    observation_date: date
    sunset: datetime
    moon_age_hours: float
    elongation: float
    moon_altitude: float
    moon_azimuth: float
    sun_altitude: float
    sun_azimuth: float
    azimuth_difference: float
    arc_of_vision: float
    moonset_after_sunset_minutes: float
    visibility_status: str


@dataclass
class MonthResult:
    hijri_year: int
    hijri_month: int
    start_date: date
    end_date: date
    length: int
    crescent: CrescentObservation
    rule: str


# ---------------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------------

def jd_from_datetime(dt: datetime) -> float:
    """Convert timezone-aware datetime to Swiss Ephemeris Julian day UT."""
    dt_utc = dt.astimezone(ZoneInfo("UTC"))
    hour = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3_600_000_000.0
    )
    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour,
        swe.GREG_CAL,
    )


def datetime_from_jd(jd: float, tz: ZoneInfo = TIMEZONE) -> datetime:
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    whole_seconds = int(h * 3600)
    microseconds = int(round((h * 3600 - whole_seconds) * 1_000_000))

    if microseconds >= 1_000_000:
        whole_seconds += 1
        microseconds -= 1_000_000

    result = datetime(y, m, d) + timedelta(
        seconds=whole_seconds,
        microseconds=microseconds,
    )
    return result.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)


def format_dt(dt: datetime) -> str:
    return dt.astimezone(TIMEZONE).isoformat()


def normalize_angle(deg: float) -> float:
    return deg % 360.0


def angular_difference(a: float, b: float) -> float:
    d = abs(normalize_angle(a) - normalize_angle(b))
    return min(d, 360.0 - d)


def parse_db_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def sql_int(value: str) -> int:
    return int(value)


# ---------------------------------------------------------------------------
# SUNRISE / SUNSET
# ---------------------------------------------------------------------------

def calc_sun_event(day: date, rise: bool) -> datetime:
    """
    Calculate sunrise/sunset directly with Swiss Ephemeris.

    This is used instead of requiring Sun_Position to exist for all
    historical/future years.
    """
    midnight_local = datetime.combine(day, datetime.min.time()).replace(
        tzinfo=TIMEZONE
    )
    jd_ut = jd_from_datetime(midnight_local)

    geopos = (LONGITUDE, LATITUDE, 0.0)
    rsmi = swe.CALC_RISE if rise else swe.CALC_SET

    result = swe.rise_trans(
        jd_ut,
        swe.SUN,
        rsmi,
        geopos,
        0.0,
        1013.25,
        swe.FLG_SWIEPH,
    )

    # Python bindings normally return (retflag, tret)
    event_jd = result[1][0]
    return datetime_from_jd(event_jd)


def sunset(day: date) -> datetime:
    return calc_sun_event(day, rise=False)


def sunrise(day: date) -> datetime:
    return calc_sun_event(day, rise=True)


# ---------------------------------------------------------------------------
# SOLAR/LUNAR POSITION
# ---------------------------------------------------------------------------

def calc_position(body: int, dt: datetime) -> tuple[float, float, float]:
    """
    Return geocentric ecliptic longitude, latitude, distance.

    Topocentric correction is handled separately where needed.
    """
    jd = jd_from_datetime(dt)
    xx, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return xx[0], xx[1], xx[2]


def calc_topocentric_horizontal(
    body: int,
    dt: datetime,
) -> tuple[float, float]:
    """
    Return topocentric altitude and azimuth in degrees.
    """
    jd = jd_from_datetime(dt)

    swe.set_topo(LONGITUDE, LATITUDE, 0.0)

    xx, _ = swe.calc_ut(
        jd,
        body,
        swe.FLG_SWIEPH
        | swe.FLG_EQUATORIAL
        | swe.FLG_TOPOCTR,
    )

    # Equatorial RA/Dec are in xx[0], xx[1].
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    sidereal = swe.sidtime(jd) * 15.0
    ramc = sidereal + LONGITUDE

    # swe.azalt expects:
    # (julday, flag, geopos, atpress, attemp, xin)
    # xin = [RA, Dec, distance]
    azalt = swe.azalt(
        jd,
        swe.EQU2HOR,
        (LONGITUDE, LATITUDE, 0.0),
        0.0,
        15.0,
        (xx[0], xx[1], xx[2]),
    )

    # Swiss Ephemeris returns azimuth measured from south toward west
    # in its standard convention. Convert to north-clockwise.
    az_swiss = azalt[0]
    altitude = azalt[1]
    azimuth = normalize_angle(az_swiss + 180.0)

    return altitude, azimuth


# ---------------------------------------------------------------------------
# NEW MOON SEARCH
# ---------------------------------------------------------------------------

def sun_moon_elongation(jd_ut: float) -> float:
    sun, _ = swe.calc_ut(jd_ut, swe.SUN, swe.FLG_SWIEPH)
    moon, _ = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SWIEPH)
    return normalize_angle(moon[0] - sun[0])


def signed_elongation(jd_ut: float) -> float:
    """
    Signed Moon-Sun longitude separation in (-180, +180].
    """
    x = sun_moon_elongation(jd_ut)
    if x > 180.0:
        x -= 360.0
    return x


def find_new_moon_near(target_local: datetime) -> datetime:
    """
    Find the nearest astronomical conjunction using a robust daily bracket
    followed by bisection.

    This intentionally does not depend on Tithi_Transition, because the
    historical database may not contain transitions for the entire range.
    """
    target_jd = jd_from_datetime(target_local)

    # Search +/- 20 days.
    step = 0.25
    left = target_jd - 20.0
    prev_jd = left
    prev_value = signed_elongation(prev_jd)

    brackets = []

    jd = left + step
    while jd <= target_jd + 20.0:
        value = signed_elongation(jd)

        # A sign crossing indicates a conjunction.
        if prev_value == 0.0 or value == 0.0 or prev_value * value < 0.0:
            brackets.append((prev_jd, jd))

        prev_jd = jd
        prev_value = value
        jd += step

    if not brackets:
        raise RuntimeError(
            f"Could not find astronomical new moon near {target_local}"
        )

    best = None

    for a, b in brackets:
        fa = signed_elongation(a)
        fb = signed_elongation(b)

        if fa == 0.0:
            root = a
        elif fb == 0.0:
            root = b
        else:
            for _ in range(70):
                mid = (a + b) / 2.0
                fm = signed_elongation(mid)

                if abs(fm) < 1e-9:
                    a = b = mid
                    break

                if fa * fm <= 0.0:
                    b = mid
                    fb = fm
                else:
                    a = mid
                    fa = fm

            root = (a + b) / 2.0

        candidate = datetime_from_jd(root)
        distance = abs((candidate - target_local).total_seconds())

        if best is None or distance < best[0]:
            best = (distance, candidate)

    return best[1]


# ---------------------------------------------------------------------------
# CRESCENT VISIBILITY
# ---------------------------------------------------------------------------

def moonset_after_sunset(
    observation_date: date,
    sunset_dt: datetime,
) -> float:
    """
    Calculate moonset after the day's sunset.

    Returns minutes:
      > 0  moon sets after sunset
      < 0  moon already set before sunset

    A direct rise/set search is used. If Swiss Ephemeris cannot find a
    crossing in the expected interval, a numerical altitude scan is used.
    """
    jd_sunset = jd_from_datetime(sunset_dt)
    geopos = (LONGITUDE, LATITUDE, 0.0)

    try:
        result = swe.rise_trans(
            jd_sunset - 0.25,
            swe.MOON,
            swe.CALC_SET,
            geopos,
            0.0,
            1013.25,
            swe.FLG_SWIEPH,
        )
        moonset_jd = result[1][0]
        moonset_dt = datetime_from_jd(moonset_jd)

        delta = (moonset_dt - sunset_dt).total_seconds() / 60.0

        # Reject a crossing obviously belonging to another day.
        if -720.0 <= delta <= 720.0:
            return delta
    except Exception:
        pass

    # Fallback numerical scan.
    start = sunset_dt - timedelta(hours=3)
    prev_alt = calc_topocentric_horizontal(swe.MOON, start)[0]
    prev_t = start

    for minutes in range(5, 13 * 60 + 1, 5):
        t = start + timedelta(minutes=minutes)
        alt = calc_topocentric_horizontal(swe.MOON, t)[0]

        if prev_alt >= 0.0 and alt < 0.0:
            lo = prev_t
            hi = t

            for _ in range(30):
                mid = lo + (hi - lo) / 2
                mid_alt = calc_topocentric_horizontal(swe.MOON, mid)[0]

                if mid_alt >= 0.0:
                    lo = mid
                else:
                    hi = mid

            moonset_dt = lo + (hi - lo) / 2
            return (moonset_dt - sunset_dt).total_seconds() / 60.0

        prev_alt = alt
        prev_t = t

    return -9999.0


def classify_crescent(
    moon_age_hours: float,
    elongation: float,
    moon_altitude: float,
    arc_of_vision: float,
    moonset_after_sunset_minutes: float,
) -> str:
    """
    Deliberately approximate visibility classifier.

    It is intended for calendar construction, not religious adjudication.

    LIKELY:
        several favorable geometric indicators.

    POSSIBLE:
        intermediate geometry.

    UNLIKELY:
        weak/negative geometry.
    """

    score = 0

    if moon_age_hours >= 18.0:
        score += 1
    if moon_age_hours >= 24.0:
        score += 1

    if elongation >= 8.0:
        score += 1
    if elongation >= 10.0:
        score += 1

    if moon_altitude >= 5.0:
        score += 1
    if moon_altitude >= 8.0:
        score += 1

    if arc_of_vision >= 5.0:
        score += 1
    if arc_of_vision >= 7.0:
        score += 1

    if moonset_after_sunset_minutes >= 20.0:
        score += 1
    if moonset_after_sunset_minutes >= 40.0:
        score += 1

    # Hard exclusions.
    if elongation < 6.0 or moon_altitude < 2.0:
        return "UNLIKELY"

    if score >= 7:
        return "LIKELY"
    if score >= 4:
        return "POSSIBLE"
    return "UNLIKELY"


def crescent_observation(
    month_start: date,
    previous_month_end: date | None = None,
    new_moon_hint: datetime | None = None,
) -> CrescentObservation:
    """
    Evaluate the crescent on the evening immediately before a candidate
    lunar month begins.

    If month_start is D, the normal observation evening is D-1.
    """
    observation_date = month_start - timedelta(days=1)
    sunset_dt = sunset(observation_date)

    if new_moon_hint is None:
        # New moon is usually near the end of the previous lunar month.
        target = datetime.combine(
            observation_date,
            datetime.min.time(),
        ).replace(tzinfo=TIMEZONE)
        new_moon = find_new_moon_near(target)
    else:
        new_moon = new_moon_hint

    moon_age_hours = (
        (sunset_dt - new_moon).total_seconds() / 3600.0
    )

    moon_altitude, moon_azimuth = calc_topocentric_horizontal(
        swe.MOON,
        sunset_dt,
    )
    sun_altitude, sun_azimuth = calc_topocentric_horizontal(
        swe.SUN,
        sunset_dt,
    )

    elongation = angular_difference(
        moon_azimuth, sun_azimuth
    )

    # For visibility we need actual angular Moon-Sun separation, not just
    # azimuth difference.
    moon_ecl_lon, moon_ecl_lat, _ = calc_position(swe.MOON, sunset_dt)
    sun_ecl_lon, sun_ecl_lat, _ = calc_position(swe.SUN, sunset_dt)

    ecliptic_elongation = angular_difference(
        moon_ecl_lon,
        sun_ecl_lon,
    )

    azimuth_difference = angular_difference(
        moon_azimuth,
        sun_azimuth,
    )

    # "Arc of Vision" is approximated here as the Moon altitude above the
    # Sun's altitude at sunset. Positive means the Moon is higher.
    arc_of_vision = moon_altitude - sun_altitude

    moonset_minutes = moonset_after_sunset(
        observation_date,
        sunset_dt,
    )

    status = classify_crescent(
        moon_age_hours=moon_age_hours,
        elongation=ecliptic_elongation,
        moon_altitude=moon_altitude,
        arc_of_vision=arc_of_vision,
        moonset_after_sunset_minutes=moonset_minutes,
    )

    return CrescentObservation(
        new_moon_local=new_moon,
        observation_date=observation_date,
        sunset=sunset_dt,
        moon_age_hours=moon_age_hours,
        elongation=ecliptic_elongation,
        moon_altitude=moon_altitude,
        moon_azimuth=moon_azimuth,
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        azimuth_difference=azimuth_difference,
        arc_of_vision=arc_of_vision,
        moonset_after_sunset_minutes=moonset_minutes,
        visibility_status=status,
    )


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def load_anchors(conn: sqlite3.Connection) -> dict[int, Anchor]:
    rows = conn.execute(
        """
        SELECT
            Hijri_Year,
            Ramadan_Start_Date,
            Ramadan_End_Date,
            Shawwal_Start_Date,
            Tabular_Eid_Ul_Fitr_Date,
            Ramadan_Days
        FROM Ramadan
        ORDER BY CAST(Hijri_Year AS INTEGER)
        """
    ).fetchall()

    if not rows:
        raise RuntimeError("Ramadan table is empty.")

    anchors: dict[int, Anchor] = {}

    for row in rows:
        y = int(row[0])
        anchors[y] = Anchor(
            hijri_year=y,
            ramadan_start=parse_db_date(row[1]),
            ramadan_end=parse_db_date(row[2]),
            shawwal_start=parse_db_date(row[3]),
            tabular_eid=parse_db_date(row[4]),
            ramadan_days=int(row[5]),
        )

    # Check the specific project anchor.
    if ANCHOR_HIJRI_YEAR not in anchors:
        raise RuntimeError(
            f"Ramadan table does not contain Hijri year "
            f"{ANCHOR_HIJRI_YEAR}."
        )

    if anchors[ANCHOR_HIJRI_YEAR].ramadan_start != ANCHOR_RAMADAN_START:
        raise RuntimeError(
            "Configured Ramadan anchor does not match Ramadan table: "
            f"{ANCHOR_HIJRI_YEAR}-09-01 = "
            f"{anchors[ANCHOR_HIJRI_YEAR].ramadan_start}, expected "
            f"{ANCHOR_RAMADAN_START}."
        )

    # Internal Ramadan-table consistency.
    years = sorted(anchors)

    for y in years:
        a = anchors[y]

        if a.ramadan_days not in (29, 30):
            raise RuntimeError(
                f"Invalid Ramadan_Days for {y}: {a.ramadan_days}"
            )

        if (a.ramadan_end - a.ramadan_start).days + 1 != a.ramadan_days:
            raise RuntimeError(
                f"Ramadan table inconsistency for {y}: "
                "Ramadan_Days does not match dates."
            )

        if a.shawwal_start != a.ramadan_end + timedelta(days=1):
            raise RuntimeError(
                f"Ramadan/Shawwal boundary inconsistency for {y}."
            )

    # Check Eid table, but do not require every row to exist.
    try:
        eid_rows = conn.execute(
            """
            SELECT Hijri_Year, Date
            FROM Eid_Ul_Fitr
            """
        ).fetchall()
        eid = {int(r[0]): parse_db_date(r[1]) for r in eid_rows}
    except sqlite3.OperationalError:
        eid = {}

    for y, a in anchors.items():
        if y in eid and eid[y] != a.shawwal_start:
            # The two independent anchor calculations can differ by one
            # civil day.  Per project policy, do NOT abort and do NOT claim
            # that either date is historically exact.  When they disagree,
            # choose the EARLIEST date.
            earliest = min(a.shawwal_start, eid[y])

            print(
                f"  WARNING: Eid_Ul_Fitr/Ramadan disagreement for {y}: "
                f"Ramadan={a.shawwal_start}, Eid_Ul_Fitr={eid[y]}; "
                f"choosing earliest date {earliest}."
            )

            # Keep the Ramadan record internally intact, but use the
            # earliest independent anchor as the effective Shawwal anchor.
            anchors[y] = Anchor(
                hijri_year=a.hijri_year,
                ramadan_start=a.ramadan_start,
                ramadan_end=earliest - timedelta(days=1),
                shawwal_start=earliest,
                tabular_eid=earliest,
                ramadan_days=(earliest - a.ramadan_start).days,
            )

            if anchors[y].ramadan_days not in (29, 30):
                raise RuntimeError(
                    f"Cannot reconcile Ramadan/Eid dates for {y}: "
                    f"earliest Shawwal date {earliest} would make Ramadan "
                    f"{anchors[y].ramadan_days} days."
                )

    return anchors


# ---------------------------------------------------------------------------
# ANCHOR-BASED YEAR GENERATION
# ---------------------------------------------------------------------------

def candidate_length_from_crescent(
    start_date: date,
) -> tuple[int, CrescentObservation]:
    obs = crescent_observation(start_date)
    return DEFAULT_LENGTH[obs.visibility_status], obs


def month_sequence_for_year(hijri_year: int) -> list[int]:
    """
    Months from Ramadan of Y through Sha'ban of Y+1.

    This sequence has exactly 12 months:
      09,10,11,12,01,02,03,04,05,06,07,08
    """
    return [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]


def enumerate_length_vectors(total_days: int) -> list[tuple[int, ...]]:
    """
    Enumerate all 12-month 29/30-day combinations whose total equals
    the exact interval between two Ramadan anchors.

    There are at most 4096 combinations.
    """
    results = []

    for bits in itertools.product((29, 30), repeat=12):
        if sum(bits) == total_days:
            results.append(bits)

    return results


def choose_length_vector(
    preferred: list[int],
    statuses: list[str],
    total_days: int,
) -> tuple[int, ...]:
    """
    Choose the 29/30 sequence closest to the astronomical preferences while
    obeying the hard Ramadan-to-Ramadan anchor interval.

    Cost:
      LIKELY + 29 = 0
      LIKELY + 30 = 2
      POSSIBLE + 30 = 0
      POSSIBLE + 29 = 1
      UNLIKELY + 30 = 0
      UNLIKELY + 29 = 2

    A small transition penalty discourages unnecessary oscillation.
    """
    candidates = enumerate_length_vectors(total_days)

    if not candidates:
        raise RuntimeError(
            f"No 29/30 month sequence can produce {total_days} days "
            f"between Ramadan anchors."
        )

    def cost(vector: tuple[int, ...]) -> float:
        score = 0.0

        for p, s, actual in zip(preferred, statuses, vector):
            if s == "LIKELY":
                if actual != 29:
                    score += 2.0
            elif s == "POSSIBLE":
                if actual != 30:
                    score += 1.0
            else:
                if actual != 30:
                    score += 2.0

        # Very mild regularity penalty.
        for a, b in zip(vector, vector[1:]):
            if a == b == 29:
                score += 0.02

        return score

    return min(candidates, key=cost)


def generate_year(
    y: int,
    current_anchor: Anchor,
    next_anchor: Anchor,
) -> list[MonthResult]:
    """
    Generate the 12 lunar months from Ramadan Y through Sha'ban Y+1.

    Ramadan Y and Ramadan Y+1 are hard anchors. The exact Gregorian
    interval determines the total number of days available to the 12
    months. Astronomical crescent estimates select the preferred lengths;
    the constrained solver reconciles those preferences with the anchors.
    """
    total_days = (
        next_anchor.ramadan_start - current_anchor.ramadan_start
    ).days

    if total_days not in (354, 355):
        raise RuntimeError(
            f"Unexpected Hijri year length for {y}: {total_days} days. "
            "Expected 354 or 355."
        )

    months = month_sequence_for_year(y)

    starts: list[date] = []
    current = current_anchor.ramadan_start

    for month in months:
        starts.append(current)
        # Temporary placeholder; final dates come from selected vector.
        current += timedelta(days=29)

    observations: list[CrescentObservation] = []
    preferred: list[int] = []
    statuses: list[str] = []

    print(f"  Astronomical evaluation for Hijri {y}...")

    for i, month in enumerate(months):
        obs = crescent_observation(starts[i])
        observations.append(obs)
        length = DEFAULT_LENGTH[obs.visibility_status]
        preferred.append(length)
        statuses.append(obs.visibility_status)

    vector = choose_length_vector(
        preferred=preferred,
        statuses=statuses,
        total_days=total_days,
    )

    results: list[MonthResult] = []

    current = current_anchor.ramadan_start

    for i, month in enumerate(months):
        length = vector[i]
        start = current
        end = current + timedelta(days=length - 1)

        if month == 9:
            rule = (
                "Ramadan table anchor; month length constrained by "
                "Ramadan-to-next-Ramadan anchor interval"
            )
        elif month == 10 and y in anchors_global:
            rule = (
                "Eid_Ul_Fitr/Ramadan Shawwal anchor; reconciled with "
                "astronomical crescent estimate"
            )
        else:
            rule = (
                f"Astronomical crescent estimate "
                f"{statuses[i]} reconciled with hard Ramadan anchors"
            )

        results.append(
            MonthResult(
                hijri_year=y,
                hijri_month=month,
                start_date=start,
                end_date=end,
                length=length,
                crescent=observations[i],
                rule=rule,
            )
        )

        current = end + timedelta(days=1)

    # Final hard check.
    if current != next_anchor.ramadan_start:
        raise RuntimeError(
            f"Internal generation error for Hijri {y}: "
            f"generated next Ramadan at {current}, expected "
            f"{next_anchor.ramadan_start}."
        )

    # Ramadan length must agree with anchor table.
    ramadan_result = results[0]
    if ramadan_result.length != current_anchor.ramadan_days:
        # The anchor table itself is authoritative. If the constrained
        # astronomical sequence disagrees, force Ramadan to the anchored
        # length and re-solve the remaining 11 months.
        fixed_ramadan = current_anchor.ramadan_days

        remaining_total = total_days - fixed_ramadan
        remaining_preferred = preferred[1:]
        remaining_statuses = statuses[1:]

        candidates = enumerate_length_vectors(remaining_total)
        if not candidates:
            raise RuntimeError(
                f"Cannot reconcile Ramadan length for Hijri {y}."
            )

        def remaining_cost(v):
            score = 0.0
            for p, s, actual in zip(
                remaining_preferred,
                remaining_statuses,
                v,
            ):
                if s == "LIKELY" and actual != 29:
                    score += 2.0
                elif s == "POSSIBLE" and actual != 30:
                    score += 1.0
                elif s == "UNLIKELY" and actual != 30:
                    score += 2.0
            return score

        chosen_remaining = min(candidates, key=remaining_cost)
        vector = (fixed_ramadan,) + chosen_remaining

        results.clear()
        current = current_anchor.ramadan_start

        for i, month in enumerate(months):
            length = vector[i]
            start = current
            end = current + timedelta(days=length - 1)

            if month == 9:
                rule = (
                    "Ramadan table hard anchor; Ramadan_Days enforced; "
                    "astronomical crescent used only as supporting evidence"
                )
            else:
                rule = (
                    f"Astronomical crescent estimate "
                    f"{statuses[i]} reconciled with Ramadan anchors"
                )

            results.append(
                MonthResult(
                    hijri_year=y,
                    hijri_month=month,
                    start_date=start,
                    end_date=end,
                    length=length,
                    crescent=observations[i],
                    rule=rule,
                )
            )

            current = end + timedelta(days=1)

    # Shawwal must exactly equal the Eid table anchor when present.
    shawwal = results[1]
    if shawwal.start_date != current_anchor.shawwal_start:
        raise RuntimeError(
            f"Shawwal anchor mismatch for Hijri {y}: "
            f"generated {shawwal.start_date}, expected "
            f"{current_anchor.shawwal_start}."
        )

    return results


# Global reference used only to annotate rules.
anchors_global: dict[int, Anchor] = {}


# ---------------------------------------------------------------------------
# FALLBACK MONTH GENERATION
# ---------------------------------------------------------------------------

def build_fallback_year(
    y: int,
    current_anchor: Anchor,
    next_anchor: Anchor,
) -> list[MonthResult]:
    """
    Emergency fallback.

    This is used only if astronomical evaluation fails for one or more
    months. It preserves the hard Ramadan/Eid anchors and constructs a
    valid 29/30-day lunar year using the standard tabular-like pattern
    closest to the anchor interval.

    The fallback never pretends that its dates are exact observations.
    """
    total_days = (
        next_anchor.ramadan_start - current_anchor.ramadan_start
    ).days

    months = month_sequence_for_year(y)

    # Common tabular-like pattern beginning with Ramadan:
    # 30,29,30,29,..., with the final month adjusted if necessary.
    base = [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29]

    candidates = enumerate_length_vectors(total_days)

    def fallback_cost(v):
        return sum(
            0 if a == b else 1
            for a, b in zip(base, v)
        )

    vector = min(candidates, key=fallback_cost)

    results = []
    current = current_anchor.ramadan_start

    for i, month in enumerate(months):
        length = vector[i]
        start = current
        end = current + timedelta(days=length - 1)

        try:
            obs = crescent_observation(start)
        except Exception:
            # Minimal placeholder observation. The database fields are
            # NOT interpreted as an assertion of visibility.
            obs = CrescentObservation(
                new_moon_local=start.replace(tzinfo=TIMEZONE),
                observation_date=start - timedelta(days=1),
                sunset=sunset(start - timedelta(days=1)),
                moon_age_hours=0.0,
                elongation=0.0,
                moon_altitude=0.0,
                moon_azimuth=0.0,
                sun_altitude=0.0,
                sun_azimuth=0.0,
                azimuth_difference=0.0,
                arc_of_vision=0.0,
                moonset_after_sunset_minutes=0.0,
                visibility_status="UNLIKELY",
            )

        results.append(
            MonthResult(
                hijri_year=y,
                hijri_month=month,
                start_date=start,
                end_date=end,
                length=length,
                crescent=obs,
                rule=(
                    "FALLBACK: astronomical evaluation unavailable; "
                    "29/30-day sequence constrained by Ramadan anchors; "
                    "dates are approximate"
                ),
            )
        )

        current = end + timedelta(days=1)

    if current != next_anchor.ramadan_start:
        raise RuntimeError(
            f"Fallback failed to reach next Ramadan anchor for {y}."
        )

    if results[0].length != current_anchor.ramadan_days:
        # Rebuild with Ramadan fixed and distribute remaining days.
        remaining_total = total_days - current_anchor.ramadan_days
        remaining_candidates = enumerate_length_vectors(remaining_total)

        if not remaining_candidates:
            raise RuntimeError(
                f"Fallback cannot satisfy Ramadan_Days for {y}."
            )

        remaining_base = base[1:]

        def rcost(v):
            return sum(
                0 if a == b else 1
                for a, b in zip(remaining_base, v)
            )

        chosen = min(remaining_candidates, key=rcost)
        vector = (current_anchor.ramadan_days,) + chosen

        results = []
        current = current_anchor.ramadan_start

        for i, month in enumerate(months):
            length = vector[i]
            start = current
            end = current + timedelta(days=length - 1)

            try:
                obs = crescent_observation(start)
            except Exception:
                obs = CrescentObservation(
                    new_moon_local=start.replace(tzinfo=TIMEZONE),
                    observation_date=start - timedelta(days=1),
                    sunset=sunset(start - timedelta(days=1)),
                    moon_age_hours=0.0,
                    elongation=0.0,
                    moon_altitude=0.0,
                    moon_azimuth=0.0,
                    sun_altitude=0.0,
                    sun_azimuth=0.0,
                    azimuth_difference=0.0,
                    arc_of_vision=0.0,
                    moonset_after_sunset_minutes=0.0,
                    visibility_status="UNLIKELY",
                )

            results.append(
                MonthResult(
                    hijri_year=y,
                    hijri_month=month,
                    start_date=start,
                    end_date=end,
                    length=length,
                    crescent=obs,
                    rule=(
                        "FALLBACK: Ramadan anchor and Ramadan_Days enforced; "
                        "remaining month lengths use 29/30 constrained "
                        "sequence; dates are approximate"
                    ),
                )
            )
            current = end + timedelta(days=1)

    if results[1].start_date != current_anchor.shawwal_start:
        raise RuntimeError(
            f"Fallback Shawwal mismatch for {y}: "
            f"{results[1].start_date} vs "
            f"{current_anchor.shawwal_start}"
        )

    return results


# ---------------------------------------------------------------------------
# BUILD COMPLETE MONTH LIST
# ---------------------------------------------------------------------------

def generate_all_months(
    conn: sqlite3.Connection,
    anchors: dict[int, Anchor],
) -> list[MonthResult]:
    """
    Generate each Hijri year independently.

    IMPORTANT:
    Every Hijri year is its own database transaction. A failure in one year
    is rolled back only for that year; previously successful years remain
    committed and later years continue.

    This is intentionally different from the old all-or-nothing design.
    """
    years = sorted(anchors)

    generated: list[MonthResult] = []
    successful_years = 0
    failed_years = 0

    for y in years:
        if y + 1 not in anchors:
            continue

        current_anchor = anchors[y]
        next_anchor = anchors[y + 1]

        print(
            f"\nGenerating Hijri {y}: "
            f"{current_anchor.ramadan_start} -> "
            f"{next_anchor.ramadan_start}"
        )

        try:
            year_results = generate_year(
                y,
                current_anchor,
                next_anchor,
            )

            # Keep the successful year in memory.
            generated.extend(year_results)

            successful_years += 1
            print(f"  SUCCESS: Hijri {y} generated.")

        except Exception as exc:
            failed_years += 1

            print(
                f"  WARNING: Hijri {y} failed: {exc}"
            )
            print(
                f"  Continuing with Hijri {y + 1}."
            )

    print()
    print(
        f"Generation summary: {successful_years} successful, "
        f"{failed_years} failed."
    )

    return generated


def generate_and_insert_years(
    conn: sqlite3.Connection,
    anchors: dict[int, Anchor],
    start_date: date,
    end_date: date,
) -> tuple[int, int, int]:
    """
    Generate and INSERT each Hijri year independently.

    Transaction model:
        BEGIN
        generate one Hijri year
        INSERT its daily rows
        COMMIT

    If anything fails:
        ROLLBACK only that Hijri year
        continue to the next year

    Returns:
        (successful_years, failed_years, inserted_rows)

    The database is deliberately not wiped here. The caller recreates the
    Hijri_Calendar table once before this function starts.
    """
    years = sorted(anchors)

    successful_years = 0
    failed_years = 0
    inserted_rows = 0

    for y in years:
        if y + 1 not in anchors:
            continue

        current_anchor = anchors[y]
        next_anchor = anchors[y + 1]

        # Skip years whose complete lunar interval cannot contribute to the
        # requested Gregorian range.
        if (
            next_anchor.ramadan_start < start_date
            or current_anchor.ramadan_start > end_date
        ):
            continue

        print()
        print("-" * 72)
        print(
            f"HIJRI {y}: "
            f"{current_anchor.ramadan_start} -> "
            f"{next_anchor.ramadan_start}"
        )
        print("-" * 72)

        try:
            # Everything belonging to this Hijri year is one transaction.
            conn.execute("BEGIN")

            try:
                year_results = generate_year(
                    y,
                    current_anchor,
                    next_anchor,
                )
            except Exception as primary_exc:
                # Try the fallback before giving up on this year.
                print(
                    f"  WARNING: primary astronomical generation failed: "
                    f"{primary_exc}"
                )
                print("  Trying year-level fallback...")

                year_results = build_fallback_year(
                    y,
                    current_anchor,
                    next_anchor,
                )

            # Restrict only the daily rows written for the requested
            # Gregorian range.
            year_results = filter_months_to_range(
                year_results,
                start_date,
                end_date,
            )

            year_rows = expand_to_daily_rows(year_results)
            year_rows = trim_daily_rows(
                year_rows,
                start_date,
                end_date,
            )

            if year_rows:
                insert_rows(conn, year_rows)

            conn.commit()

            successful_years += 1
            inserted_rows += len(year_rows)

            print(
                f"  COMMITTED: Hijri {y}; "
                f"{len(year_rows)} daily rows inserted."
            )

        except Exception as exc:
            # Critical point: rollback ONLY this Hijri year.
            try:
                conn.rollback()
            except Exception:
                pass

            failed_years += 1

            print(
                f"  FAILED: Hijri {y}: {exc}"
            )
            print(
                "  ROLLED BACK ONLY THIS YEAR; continuing."
            )

    return successful_years, failed_years, inserted_rows


# ---------------------------------------------------------------------------
# DAILY EXPANSION
# ---------------------------------------------------------------------------

def expand_to_daily_rows(
    months: list[MonthResult],
) -> list[tuple]:
    rows = []

    for m in months:
        d = m.start_date

        while d <= m.end_date:
            day_number = (d - m.start_date).days + 1

            # Only one astronomical observation is stored for the month
            # boundary, and it is copied to all daily rows of that month.
            # This makes the daily table self-contained.
            c = m.crescent

            rows.append(
                (
                    d.isoformat(),
                    f"{m.hijri_year:04d}",
                    f"{m.hijri_month:02d}",
                    HIJRI_MONTH_NAMES[m.hijri_month],
                    f"{day_number:02d}",

                    m.start_date.isoformat(),
                    m.end_date.isoformat(),
                    m.length,

                    format_dt(c.new_moon_local),
                    c.observation_date.isoformat(),
                    format_dt(c.sunset),

                    c.moon_age_hours,
                    c.elongation,
                    c.moon_altitude,
                    c.moon_azimuth,

                    c.sun_altitude,
                    c.sun_azimuth,

                    c.azimuth_difference,
                    c.arc_of_vision,
                    c.moonset_after_sunset_minutes,

                    c.visibility_status,
                    m.rule,
                )
            )

            d += timedelta(days=1)

    return rows


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_months(
    months: list[MonthResult],
    anchors: dict[int, Anchor],
) -> None:
    if not months:
        raise RuntimeError("No Hijri months generated.")

    months = sorted(
        months,
        key=lambda m: m.start_date,
    )

    # Every month must be 29 or 30 days.
    for m in months:
        if m.length not in (29, 30):
            raise RuntimeError(
                f"Invalid month length: {m.hijri_year}-{m.hijri_month:02d}"
            )

        if (m.end_date - m.start_date).days + 1 != m.length:
            raise RuntimeError(
                f"Date/length mismatch: "
                f"{m.hijri_year}-{m.hijri_month:02d}"
            )

    # No gaps or overlaps.
    for a, b in zip(months, months[1:]):
        if a.end_date + timedelta(days=1) != b.start_date:
            raise RuntimeError(
                f"Gap/overlap between "
                f"{a.hijri_year}-{a.hijri_month:02d} and "
                f"{b.hijri_year}-{b.hijri_month:02d}."
            )

    # Check every Ramadan anchor represented by the generated sequence.
    by_key = {
        (m.hijri_year, m.hijri_month): m
        for m in months
    }

    for y, a in anchors.items():
        key = (y, 9)

        if key not in by_key:
            continue

        m = by_key[key]

        if m.start_date != a.ramadan_start:
            raise RuntimeError(
                f"Ramadan anchor mismatch for {y}: "
                f"{m.start_date} != {a.ramadan_start}"
            )

        if m.length != a.ramadan_days:
            raise RuntimeError(
                f"Ramadan length mismatch for {y}: "
                f"{m.length} != {a.ramadan_days}"
            )

        shawwal = by_key.get((y, 10))
        if shawwal and shawwal.start_date != a.shawwal_start:
            raise RuntimeError(
                f"Shawwal anchor mismatch for {y}: "
                f"{shawwal.start_date} != {a.shawwal_start}"
            )


def filter_months_to_range(
    months: list[MonthResult],
    start_date: date,
    end_date: date,
) -> list[MonthResult]:
    return [
        m for m in months
        if m.end_date >= start_date and m.start_date <= end_date
    ]


def trim_daily_rows(
    rows: list[tuple],
    start_date: date,
    end_date: date,
) -> list[tuple]:
    return [
        r for r in rows
        if start_date <= date.fromisoformat(r[0]) <= end_date
    ]


# ---------------------------------------------------------------------------
# DATABASE WRITE
# ---------------------------------------------------------------------------

def recreate_table(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS Hijri_Calendar")

    conn.execute(
        """
        CREATE TABLE Hijri_Calendar (
            Gregorian_Date TEXT NOT NULL,
            Hijri_Year TEXT NOT NULL,
            Hijri_Month TEXT NOT NULL,
            Hijri_Month_Name TEXT NOT NULL,
            Hijri_Day TEXT NOT NULL,

            Month_Start_Local TEXT NOT NULL,
            Month_End_Local TEXT NOT NULL,
            Month_Length INTEGER NOT NULL
                CHECK (Month_Length IN (29, 30)),

            New_Moon_Local TEXT NOT NULL,
            Crescent_Observation_Date_Local TEXT NOT NULL,
            Sunset_Time_Local TEXT NOT NULL,

            Moon_Age_Hours REAL NOT NULL,
            Moon_Sun_Elongation_Degrees REAL NOT NULL,
            Moon_Altitude_At_Sunset_Degrees REAL NOT NULL,
            Moon_Azimuth_At_Sunset_Degrees REAL NOT NULL,

            Sun_Altitude_At_Sunset_Degrees REAL NOT NULL,
            Sun_Azimuth_At_Sunset_Degrees REAL NOT NULL,

            Azimuth_Difference_Degrees REAL NOT NULL,
            Arc_of_Vision_Degrees REAL NOT NULL,
            Moonset_After_Sunset_Minutes REAL NOT NULL,

            Visibility_Status TEXT NOT NULL,
            Rule_Applied TEXT NOT NULL,

            PRIMARY KEY (Gregorian_Date)
        )
        """
    )


def insert_rows(
    conn: sqlite3.Connection,
    rows: list[tuple],
) -> None:
    # Hijri_Calendar currently has exactly 22 columns.
    # Validate the Python tuple shape before touching the database.
    for row_number, row in enumerate(rows, start=1):
        if len(row) != 22:
            raise RuntimeError(
                f"Hijri_Calendar row {row_number} contains {len(row)} "
                "values; exactly 22 are required."
            )

    conn.executemany(
        """
        INSERT INTO Hijri_Calendar (
            Gregorian_Date,
            Hijri_Year,
            Hijri_Month,
            Hijri_Month_Name,
            Hijri_Day,

            Month_Start_Local,
            Month_End_Local,
            Month_Length,

            New_Moon_Local,
            Crescent_Observation_Date_Local,
            Sunset_Time_Local,

            Moon_Age_Hours,
            Moon_Sun_Elongation_Degrees,
            Moon_Altitude_At_Sunset_Degrees,
            Moon_Azimuth_At_Sunset_Degrees,

            Sun_Altitude_At_Sunset_Degrees,
            Sun_Azimuth_At_Sunset_Degrees,

            Azimuth_Difference_Degrees,
            Arc_of_Vision_Degrees,
            Moonset_After_Sunset_Minutes,

            Visibility_Status,
            Rule_Applied
        )
        VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    global anchors_global

    print("=" * 72)
    print("GENERATING ANCHORED HIJRI CALENDAR")
    print("=" * 72)
    print(f"Gregorian range : {START_DATE} to {END_DATE}")
    print(f"Location        : {LOCATION}")
    print("Date philosophy : astronomical approximation + earliest-date fallback")
    print("Exactness        : dates are NOT expected to be exact observations")
    print("Database policy  : commit each Hijri year independently")
    print()

    if not Path(DB_PATH).exists():
        raise FileNotFoundError(DB_PATH)

    conn = sqlite3.connect(DB_PATH)

    try:
        anchors = load_anchors(conn)
        anchors_global = anchors

        print(
            f"Ramadan anchors loaded: "
            f"{min(anchors)} -> {max(anchors)}"
        )

        # Recreate the destination table ONCE.
        #
        # After this point, each Hijri year is committed independently.
        # Therefore a later error cannot roll back earlier successful years.
        recreate_table(conn)
        conn.commit()

        successful_years, failed_years, inserted_rows = (
            generate_and_insert_years(
                conn,
                anchors,
                START_DATE,
                END_DATE,
            )
        )

        # Final database checks. These are informational and do NOT roll back
        # the successfully committed years.
        row_count = conn.execute(
            "SELECT COUNT(*) FROM Hijri_Calendar"
        ).fetchone()[0]

        bad_lengths = conn.execute(
            """
            SELECT COUNT(*)
            FROM Hijri_Calendar
            WHERE Month_Length NOT IN (29,30)
            """
        ).fetchone()[0]

        first_date = conn.execute(
            """
            SELECT MIN(Gregorian_Date)
            FROM Hijri_Calendar
            """
        ).fetchone()[0]

        last_date = conn.execute(
            """
            SELECT MAX(Gregorian_Date)
            FROM Hijri_Calendar
            """
        ).fetchone()[0]

        print()
        print("=" * 72)
        print("GENERATION COMPLETE")
        print("=" * 72)
        expected_rows = (END_DATE - START_DATE).days + 1

        print(f"Rows inserted   : {row_count}")
        print(f"Rows attempted  : {expected_rows}")
        print(f"First date      : {first_date}")
        print(f"Last date       : {last_date}")
        print(f"Invalid lengths : {bad_lengths}")
        print(f"Years committed : {successful_years}")
        print(f"Years failed    : {failed_years}")
        print(
            "Missing rows are expected if one or more Hijri years failed; "
            "successful years remain committed."
        )
        print()

        print("Ramadan/Eid anchor validation:")
        for y in sorted(anchors):
            a = anchors[y]

            if a.ramadan_start > END_DATE + timedelta(days=400):
                continue
            if a.ramadan_start < START_DATE - timedelta(days=400):
                continue

            row = conn.execute(
                """
                SELECT
                    Gregorian_Date,
                    Hijri_Year,
                    Hijri_Month,
                    Hijri_Day
                FROM Hijri_Calendar
                WHERE Gregorian_Date = ?
                """,
                (a.ramadan_start.isoformat(),),
            ).fetchone()

            if row:
                print(
                    f"  {y} Ramadan 1 : "
                    f"{row[0]}  "
                    f"Shawwal 1 = {a.shawwal_start}"
                )

        print()
        print(
            "NOTE: The astronomical fields are supporting calculations. "
            "They should not be interpreted as proof of an actual local "
            "crescent sighting."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
