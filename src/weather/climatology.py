"""
Day-of-year climatology and Excess Heat Factor (EHF).

WHY THIS EXISTS
---------------
The previous heat-event test was an absolute threshold: UTCI >= 30.3 for two
or more consecutive days. Measured against 30 years of real local weather,
that threshold fires on 69 days a year, and it sits *below* the May average
of 33.6 - so the entire hot season registered as one continuous heatwave.
A season is not an event.

WHAT REPLACES IT
----------------
The Excess Heat Factor (Nairn & Fawcett, Australian Bureau of Meteorology;
the operational basis of Australia's national heatwave service). It is a
second, independent published method - not another reading of the same
mortality paper - and it encodes the thing an absolute threshold cannot:

    EHI_significance  = T3 - T95      is it hot by climatological standards?
    EHI_acclimatisation = T3 - T30    is it hot *compared to recent weeks*?

    EHF = EHI_sig x max(1, EHI_accl)

where T3 is the three-day mean ending today, T95 the long-term 95th
percentile, and T30 the mean of the preceding thirty days.

The acclimatisation term is the whole point. After three weeks of heat the
body has adapted and T30 has risen, so EHI_accl collapses towards or below
1 and EHF falls back - exactly the intuition that a long hot season stops
being an emergency. The same absolute temperature arriving suddenly in
March, against a cool preceding month, produces a large EHF. Heat kills on
the way up, not on the plateau, and EHF is built around that.

Severity is expressed relative to the local historical distribution of
positive EHF, so "severe" means severe *for this city*.
"""

import os

import numpy as np
import pandas as pd

CLIMATOLOGY_FILE = "data/cleaned/utci_climatology.csv"
HISTORY_FILE = "data/cleaned/utci_daily_history.csv"
TRAILING_FILE = "data/cleaned/utci_trailing_normals.csv"

SIGNIFICANCE_PERCENTILE = 95

# The significance threshold is the 95th percentile FOR THIS DATE, floored
# at an absolute level.
#
# The original version used a single annual 95th percentile, following
# Nairn & Fawcett directly. In a climate with this large a seasonal cycle
# that is a structural failure: the annual figure here is 46.3, which is
# a May number. A September day 5C above its own normal reaches only
# 41.9 - still 4.4 BELOW the annual threshold - so the significance term
# went negative and the detector reported "not an event" on a day that
# was genuinely abnormal. Measured over 30 years, it caught 0.0 September
# events per year.
#
# Out-of-season heat is precisely when people are least acclimatised, so
# being blind to it is the worst possible failure mode.
#
# The day-of-year percentile alone would go too far the other way and let
# a mild winter warm spell qualify, so it is floored: a day must be both
# unusual FOR THE DATE and hot enough in absolute terms to matter. The
# floor is set where the dose-response curve shows mortality beginning to
# climb, not at a round number.
#
# Measured effect: 11.6 event days/yr (was 16.8), September 1.4/yr (was
# 0.0), and the 2010 acute week is still caught on 6 of its 7 days.
SIGNIFICANCE_FLOOR_UTCI = 40.0

# Weight on the overnight anomaly when forming the effective daily heat
# load:  effective UTCI = afternoon UTCI + w x max(0, night anomaly)
#
# WHY A NIGHT TERM AT ALL - decided before any fitting:
#   - A hot night denies the body its recovery window; this is the
#     standard physiological account of why multi-day heat kills.
#   - Every operational heat-health system that predicts mortality uses
#     a night-time term (France pairs 3-day minimum with 3-day maximum;
#     the US HeatRisk tool explicitly includes overnight lows).
#   - It carries information the daytime figure does not: across this
#     city's 30-year record the day and night anomalies correlate only
#     0.46.
#
# WHY 0.5, AND HOW MUCH TO TRUST IT: calibrated against the 2010 event,
# the single best-measured heat-mortality episode available here
# (1,344 excess deaths independently measured for May 2010). At w=0.5
# the model returns 1,354. That is ONE parameter fitted to ONE
# observation - calibrated, not validated. It survives a second,
# independent check: it puts the annual heat-attributable burden at
# 3.1% of all deaths, just under the 3.58% the source study measured
# for days above 38 C, which is the right side to land on since only
# above-normal heat is counted here. The weight is below 1.0 because the
# daytime term is a full thermal index including solar load while the
# night term is plain air temperature - they are not the same units.
NIGHT_ANOMALY_WEIGHT = 0.5

SHORT_WINDOW_DAYS = 3
ACCLIMATISATION_WINDOW_DAYS = 30

# Severity bands, as multiples of the historical 85th percentile of
# positive EHF (the BOM convention).
SEVERE_MULTIPLE = 1.0
EXTREME_MULTIPLE = 3.0


class Climatology:
    """Long-term local UTCI norms, loaded once and reused."""

    def __init__(self, history_file=HISTORY_FILE,
                 climatology_file=CLIMATOLOGY_FILE):

        if not os.path.exists(history_file):
            raise FileNotFoundError(
                f"{history_file} not found - run scripts/build_climatology.py"
            )

        self.history = pd.read_csv(history_file, parse_dates=["date"])
        self.by_day_of_year = pd.read_csv(climatology_file).set_index(
            "day_of_year"
        )

        # Year-specific normals. Indexed by (year, day-of-year) so the
        # same lookup serves a live forecast and a historical replay.
        trailing = pd.read_csv(TRAILING_FILE)
        self.trailing_normals = trailing.set_index(["year", "day_of_year"])
        self.latest_normal_year = int(trailing["year"].max())

        # Kept for reference and for anything that still wants a single
        # number, but the detector uses the date-specific threshold below.
        self.t95 = float(
            np.percentile(self.history["utci_c"], SIGNIFICANCE_PERCENTILE)
        )

        self.significance_by_day = (
            self.by_day_of_year["utci_p95"]
            .clip(lower=SIGNIFICANCE_FLOOR_UTCI)
        )

        self.ehf_reference = self._historical_ehf_reference()

    def significance_threshold(self, date):
        """
        The temperature a day must beat to count as significantly hot
        here, on this date. See SIGNIFICANCE_FLOOR_UTCI.
        """

        doy = min(pd.Timestamp(date).dayofyear, 365)

        return float(self.significance_by_day.loc[doy])

    def significance_series(self, dates):
        """Per-day significance thresholds for a sequence of dates."""

        return np.array([self.significance_threshold(d) for d in dates])

    def _trailing_row(self, date):
        """
        The normal as of this date: the average of the years immediately
        preceding it. A date beyond the record uses the most recent
        window available, which is what a live forecast needs.
        """

        stamp = pd.Timestamp(date)
        doy = min(stamp.dayofyear, 365)
        year = min(stamp.year, self.latest_normal_year)

        while year >= self.latest_normal_year - 40:
            if (year, doy) in self.trailing_normals.index:
                return self.trailing_normals.loc[(year, doy)]
            year -= 1

        raise KeyError(f"no trailing normal available for {date}")

    def normal_for(self, date):
        """
        The normal and spread of UTCI for this calendar date.

        The central value is the trailing normal - what was normal in the
        years leading up to this date - because that is what the
        population is acclimatised to. The percentiles come from the full
        record, which the tail needs for a stable estimate.
        """

        doy = min(pd.Timestamp(date).dayofyear, 365)
        row = self.by_day_of_year.loc[doy]
        trailing = self._trailing_row(date)

        return {
            "utci_normal": float(trailing["utci_normal"]),
            "utci_normal_full_record": float(row["utci_mean"]),
            "utci_p90": float(row["utci_p90"]),
            "utci_p95": float(row["utci_p95"]),
            "utci_sd": float(row["utci_sd"]),
        }

    def anomaly(self, date, utci_c):
        """How far above the local normal for this date, in degrees."""

        return utci_c - self.normal_for(date)["utci_normal"]

    def night_normal_for(self, date):
        """Trailing mean overnight temperature for this calendar date."""

        return float(self._trailing_row(date)["night_temp_normal"])

    def effective_utci(self, date, utci_c, night_temp_c=None):
        """
        Daytime thermal stress plus the share of overnight heat that
        denies the body its recovery window.

        Only heat ABOVE the normal night counts - an ordinary night, however
        warm in absolute terms, is one the population is adapted to.
        Returns the daytime value unchanged when no overnight reading is
        available, so a missing input degrades rather than breaks.
        """

        if night_temp_c is None:
            return utci_c

        night_anomaly = max(
            0.0, night_temp_c - self.night_normal_for(date)
        )

        return utci_c + NIGHT_ANOMALY_WEIGHT * night_anomaly

    def _historical_ehf_reference(self):
        """
        The 85th percentile of positive EHF across the full historical
        record - the yardstick severity is expressed against.
        """

        history = self.history.sort_values("date").reset_index(drop=True)

        ehf = compute_ehf_series(
            history["utci_c"].to_numpy(),
            t95=self.significance_series(history["date"]),
        )

        positive = ehf[ehf > 0]

        if len(positive) == 0:
            return 1.0

        return float(np.percentile(positive, 85))

    def severity(self, ehf):
        """Severity label for an EHF value, relative to local history."""

        if ehf is None or ehf <= 0:
            return "none"

        ratio = ehf / self.ehf_reference

        if ratio >= EXTREME_MULTIPLE:
            return "extreme"
        if ratio >= SEVERE_MULTIPLE:
            return "severe"
        return "low_intensity"


def compute_ehf_series(utci_values, t95):
    """
    Excess Heat Factor for every position in a daily UTCI series.

    `t95` is the significance threshold: either one number, or one per
    day (an array the same length as the series) so the threshold can
    follow the season. Positions without a full 30-day lookback return
    NaN rather than a value computed from a partial window.
    """

    values = np.asarray(utci_values, dtype=float)
    n = len(values)

    thresholds = np.asarray(t95, dtype=float)
    if thresholds.ndim == 0:
        thresholds = np.full(n, float(thresholds))
    elif len(thresholds) != n:
        raise ValueError(
            f"t95 has {len(thresholds)} entries for a series of {n} days"
        )

    ehf = np.full(n, np.nan)

    lookback = ACCLIMATISATION_WINDOW_DAYS + SHORT_WINDOW_DAYS

    for i in range(lookback, n):

        three_day_mean = values[i - SHORT_WINDOW_DAYS + 1: i + 1].mean()

        recent_mean = values[
            i - SHORT_WINDOW_DAYS + 1 - ACCLIMATISATION_WINDOW_DAYS:
            i - SHORT_WINDOW_DAYS + 1
        ].mean()

        significance = three_day_mean - thresholds[i]
        acclimatisation = three_day_mean - recent_mean

        ehf[i] = significance * max(1.0, acclimatisation)

    return ehf


def compute_ehf(recent_utci_values, t95):
    """
    EHF for the final day of a series. `recent_utci_values` must end on
    the day of interest and contain at least 33 days.
    """

    series = compute_ehf_series(recent_utci_values, t95)

    if len(series) == 0 or np.isnan(series[-1]):
        return None

    return float(series[-1])
