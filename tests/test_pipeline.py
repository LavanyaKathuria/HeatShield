from src.mortality import dose_response, age_structure, risk_axes
from src.mortality.heat_burden import HeatBurdenEngine, attributable_fraction
from src.weather.weather_pipeline import get_ward_weather_mortality_risk
from src.weather.heat_stress import calculate_heat_stress, _utci_stress_category
from src.weather.climatology import Climatology
from src.risk import levels, scenario

from src.mortality.age_structure import (
    CITY_POPULATION, CRUDE_DEATH_RATE_PER_1000 as CRUDE_DEATH_RATE,
)


# ======================================================================
# THERMAL STRESS
# ======================================================================

def test_utci_stress_category_matches_official_boundaries():
    """
    Regression test: an earlier version used the wrong bin-edge
    convention, which mislabeled most non-boundary values one category
    too low and made "extreme heat stress" unreachable. These are values
    strictly between boundaries, which is what the bug got wrong.
    """

    assert _utci_stress_category(27.0) == "moderate heat stress"
    assert _utci_stress_category(35.0) == "strong heat stress"
    assert _utci_stress_category(40.0) == "very strong heat stress"
    assert _utci_stress_category(47.0) == "extreme heat stress"


def test_heat_stress_reflects_humidity_not_just_temperature():
    """
    The problem statement's own example: 40C at 20% humidity must read as
    materially less dangerous than 40C at 70%, despite identical dry-bulb
    temperature.
    """

    dry = calculate_heat_stress(40, 20, 2.0, 700)
    humid = calculate_heat_stress(40, 70, 2.0, 700)

    assert humid["heat_index_c"] > dry["heat_index_c"]
    assert humid["utci_c"] > dry["utci_c"]


# ======================================================================
# DOSE-RESPONSE
# ======================================================================

def test_dose_response_curve_is_monotonic_and_grounded_at_mmt():

    mmt_utci = dose_response.CURVE_POINTS[0][0]

    assert dose_response.relative_risk(mmt_utci)["relative_risk"] == 1.0

    risks = [
        dose_response.relative_risk(point[0])["relative_risk"]
        for point in dose_response.CURVE_POINTS
    ]

    assert risks == sorted(risks)


def test_dose_response_beyond_observed_range_is_flagged():

    # Anchored off the curve rather than a literal, so the test survives
    # a rebuild of the Tmax->UTCI reprojection (it was rebuilt once, when
    # the original anchors turned out to come from a mis-timezoned
    # afternoon window).
    beyond = dose_response.MAX_OBSERVED_UTCI + 1.0

    result = dose_response.relative_risk(beyond)

    assert result["is_beyond_observed_range"] is True
    assert result["relative_risk"] > 3.08


def test_attributable_fraction_is_not_relative_risk_minus_one():
    """
    The correct attributable fraction for a cumulative-lag curve is
    1 - 1/RR, not RR - 1. At RR 3 the wrong form overstates the burden
    roughly threefold, which is what made the original engine's output
    indefensible.
    """

    utci = dose_response.CURVE_POINTS[-1][0]
    relative_risk = dose_response.relative_risk(utci)["relative_risk"]

    fraction = attributable_fraction(utci)["point"]

    assert fraction == 1.0 - 1.0 / relative_risk
    assert fraction < relative_risk - 1.0
    assert 0.0 < fraction < 1.0


# ======================================================================
# AGE AND OCCUPATION
# ======================================================================

def test_age_structure_reproduces_both_local_measurements():
    """
    The derived death rates must satisfy the two real local constraints
    they were solved from - the crude death rate, and the measured 35.5%
    elderly share of all deaths.
    """

    checks = age_structure.validate(CITY_POPULATION, CRUDE_DEATH_RATE)

    assert abs(
        checks["implied_annual_deaths"] - checks["expected_annual_deaths"]
    ) < 1.0

    assert abs(
        checks["modelled_elderly_death_share"]
        - checks["observed_elderly_death_share"]
    ) < 0.001

    # The elderly rate is SOLVED, not assumed - it falls out of the local
    # crude death rate, the measured 35.5% elderly share of deaths, and
    # the census age structure.
    #
    # Independent cross-check: take published SRS age-specific death
    # rates (65-69: 30, 70-74: 45, 75-79: 70, 80+: 120 per 1,000) and
    # weight them by this city's own 65+ age structure, and you get 56.5.
    # The model derives 57.1 by a completely different route. Two
    # independent paths agreeing to within 1% is the real validation
    # here, which is why the bound is tight rather than generous.
    assert 54.0 < checks["death_rates_per_1000"]["elderly"] < 60.0


def test_age_susceptibility_preserves_the_total():
    """
    The age split must redistribute the burden, never create or destroy
    it: the death-weighted average susceptibility has to be exactly 1.
    """

    baseline = age_structure.baseline_daily_deaths_by_age(
        CITY_POPULATION, CRUDE_DEATH_RATE
    )
    total = sum(baseline.values())
    shares = {band: value / total for band, value in baseline.items()}

    susceptibility = risk_axes.age_susceptibility(shares)

    weighted = sum(shares[b] * susceptibility[b] for b in shares)

    assert abs(weighted - 1.0) < 1e-9


def test_elderly_always_rank_above_adults_per_capita():
    """
    The defect that started the rebuild: working-age adults could rank
    above the elderly, because literature age SHARES were applied to one
    pooled total. Per-capita risk cannot invert, at any heat level.
    """

    heat_engine = HeatBurdenEngine(CITY_POPULATION)

    for utci in (44.0, 46.0, 48.0, 50.0):
        burden = heat_engine.indirect_burden(utci, 43.0)
        by_age = burden["by_age"]

        assert (
            by_age["elderly"]["excess_per_100k"]
            > by_age["adults"]["excess_per_100k"]
        )
        assert (
            by_age["elderly"]["excess_per_100k"]
            > by_age["children"]["excess_per_100k"]
        )


def test_occupation_axis_respects_the_measured_odds_ratio():

    heat_engine = HeatBurdenEngine(CITY_POPULATION)
    occupational = heat_engine.indirect_burden(48.0, 43.0)["by_occupation"]

    ratio = (
        occupational["outdoor_per_100k"] / occupational["indoor_per_100k"]
    )

    assert abs(ratio - risk_axes.OUTDOOR_ODDS_RATIO) < 0.01


# ======================================================================
# THE ZERO POINT
# ======================================================================

def test_ordinary_day_produces_no_excess_and_names_nobody():
    """
    The central fix. An ordinary day for the date must return zero, and
    must NOT name a most-at-risk group - naming one anyway is a false
    alarm dressed up as information.
    """

    heat_engine = HeatBurdenEngine(CITY_POPULATION)
    burden = heat_engine.daily_burden(45.0, 45.0)

    assert burden["indirect_all_cause"]["total"] == 0.0
    assert burden["highest_risk_group"] is None


def test_below_normal_day_is_floored_not_negative():

    heat_engine = HeatBurdenEngine(CITY_POPULATION)
    burden = heat_engine.daily_burden(38.0, 45.0)

    assert burden["indirect_all_cause"]["total"] == 0.0


def test_hot_night_increases_burden():
    """
    A hot night denies the body its recovery window, so the same daytime
    heat must carry more burden when the night does not cool.
    """

    heat_engine = HeatBurdenEngine(CITY_POPULATION)

    cool_night = heat_engine.daily_burden(48.0, 45.0, night_temp_c=28.0,
                                          night_normal_c=28.0)
    hot_night = heat_engine.daily_burden(48.0, 45.0, night_temp_c=33.0,
                                         night_normal_c=28.0)

    assert (
        hot_night["indirect_all_cause"]["total"]
        > cool_night["indirect_all_cause"]["total"]
    )


# ======================================================================
# CLIMATOLOGY AND EVENT DETECTION
# ======================================================================

def test_climatology_uses_trailing_normals():
    """
    The normal for a date must be what was normal BEFORE it, not an
    average that includes later, warmer years - otherwise a past heatwave
    is scored against a baseline the years since have caught up with.
    """

    climatology = Climatology()

    old = climatology.normal_for("2000-05-20")["utci_normal"]
    recent = climatology.normal_for("2024-05-20")["utci_normal"]

    assert recent > old


def test_ordinary_hot_season_day_is_not_a_heat_event():
    """
    The complaint that drove the redesign: three months at the seasonal
    norm is a season, not a heatwave. The acclimatisation term is what
    makes this true.
    """

    climatology = Climatology()
    history = climatology.history

    may = history[history["date"].dt.month == 5]
    typical = may["utci_c"].median()

    # A day at the May median, against a May run-up, must not register.
    from src.weather.climatology import compute_ehf_series
    import numpy as np

    flat = np.full(40, typical)
    ehf = compute_ehf_series(flat, climatology.t95)[-1]

    assert ehf <= 0
    assert climatology.severity(ehf) == "none"


# ======================================================================
# ALERT TRIGGERS AND TARGETING
# ======================================================================

def test_groups_are_triggered_independently():
    """
    Different groups trigger on different metrics, so a forecast can
    reach one group's threshold without reaching another's. A single
    shared threshold could not do this - every group's risk is the same
    attributable fraction times its own baseline, so they would all
    cross at once.
    """

    only_elderly = levels.group_levels(
        elderly_risk_per_100k=2.1,          # above the 1.7 watch line
        wbgt_c=27.0,                        # below the 29.4 work/rest line
        utci_c=36.0,                        # below the 38.0 activity line
        ehf=4.0,
        ehf_reference=11.2,
        is_heat_event=True,
    )

    assert only_elderly["elderly"] != "none"
    assert only_elderly["outdoor_workers"] == "none"
    assert only_elderly["children"] == "none"


def test_no_event_means_no_alerts_at_all():
    """
    ONE gate. A day that is not unusual for this place and date produces
    no alerts for anyone, however hot it is in absolute terms.

    An earlier version left the occupational and child triggers ungated,
    and the result was a September afternoon where the event test said
    "no event", the burden said zero, and the map still painted 45 of 48
    wards amber off an ungated WBGT threshold. In this climate "hot" is
    most of the year; a warning that fires most of the year is not a
    warning.
    """

    group_levels = levels.group_levels(
        elderly_risk_per_100k=9.0,
        wbgt_c=36.5,
        utci_c=49.0,
        ehf=None,
        ehf_reference=11.2,
        is_heat_event=False,
    )

    assert set(group_levels.values()) == {"none"}
    assert levels.overall_level(group_levels) == "none"


def test_work_rest_guidance_is_available_without_an_event():
    """
    Guidance is not an alert. The work/rest split is a fact about the
    conditions and is produced every day, including days that raise no
    alert - that is what makes gating the alerts affordable.
    """

    assert levels.work_rest_guidance(33.0) == "work_rest.25_75"
    assert levels.work_rest_guidance(30.0) == "work_rest.75_25"
    assert levels.work_rest_guidance(20.0) == "work_rest.normal"
    assert levels.work_rest_guidance(None) is None


def test_occupational_thresholds_are_the_published_standard():
    """
    These must stay ISO 7243 / NIOSH work-rest limits, not local
    percentiles. They were once set to this city's own 90th/95th/99th
    WBGT percentiles because the real limits "fired too often" - but they
    fire often because outdoor work here genuinely does exceed
    international heat limits for much of the year.
    """

    assert levels.WBGT_WORK_REST["continuous"] == 28.0
    assert levels.OUTDOOR_WBGT_C["watch"] == levels.WBGT_WORK_REST["75_25"]
    assert levels.OUTDOOR_WBGT_C["danger"] == levels.WBGT_WORK_REST["25_75"]


# ======================================================================
# REPLAY OF A REAL EVENT
# ======================================================================

def test_replaying_a_real_heatwave_reaches_danger():
    """
    End to end on weather that actually happened, through exactly the
    same engine a live forecast uses.
    """

    days = scenario.replay("may_2024")

    assert days
    assert any(day["event_severity"] in ("severe", "extreme") for day in days)

    peak = max(days, key=lambda d: d["excess_deaths"])
    assert peak["group_levels"]["elderly"] == "danger"
    assert peak["excess_deaths"] > 0

# ======================================================================
# FULL PIPELINE
# ======================================================================

def test_weather_mortality_pipeline():

    weather_df, ward_summary, citywide, records = (
        get_ward_weather_mortality_risk(forecast_days=3)
    )

    assert len(weather_df) > 0
    assert weather_df["ward_id"].nunique() == 48

    for column in (
        "utci_c", "utci_stress_category", "utci_normal_c", "utci_anomaly_c",
        "wbgt_shade_c", "heat_index_c", "tmax", "tmin",
        "afternoon_humidity_pct", "afternoon_wind_ms", "afternoon_solar_wm2",
        "alert_level", "group_levels", "elderly_per_100k",
    ):
        assert column in weather_df.columns
        assert weather_df[column].notna().all(), column

    # Citywide burden must be computed once per day, never summed across
    # wards - each ward row carries a city-scale figure, so summing 48 of
    # them would multiply the city's death toll by 48.
    assert citywide["total_excess_deaths"] == round(
        sum(record["excess_deaths"] for record in records), 1
    )
    assert len(records) == 3



