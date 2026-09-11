"""
Real, citation-backed heat-mortality dose-response curve for Ahmedabad,
reprojected from Tmax onto UTCI.

The curve (Tmax -> relative risk of all-cause mortality, gender-stratified)
is Sharma et al. 2024's actual fitted DLNM output for Ahmedabad, 2002-2018
(21-day cumulative lag, 684,142 deaths) - see research/SOURCES.md #1. It is
a real 9-point non-linear curve referenced to Ahmedabad's own Minimum
Mortality Temperature (26C), not a linear approximation and not a set of
hand-picked thresholds. Real 95% confidence intervals from the same table
are carried through end to end - "always show confidence ranges, never
false precision" only means something if the ranges are real, so these are
the paper's own reported CIs, not invented error bars.

The Tmax axis is converted to UTCI using the real historical relationship
between the two: for each Sharma et al. threshold, we looked at every real
Ahmedabad day (1995-2024, reanalysis, 10,958 days, year-round) whose Tmax fell
within +/-0.4C of that threshold, and took the mean afternoon UTCI actually
observed on those days (Pearson r=0.965 between Tmax and UTCI across the full
sample). This lets a forecast driven by the full thermal stress index
(temperature+humidity+wind+radiation) be scored against a curve that was
actually fit on temperature-mortality data, without pretending UTCI-specific
mortality data exists (it doesn't - no such study has been published).

Above the highest real anchor (UTCI 50.4C, corresponding to Tmax=45C, of
which only 13 such days occurred in 30 years), any RR value is a linear
extrapolation beyond directly observed data - this is flagged in the output,
matching Sharma et al.'s own and Hess et al.'s own caveats about how rare
events at this end of the distribution are.
"""

import numpy as np


# Each point: utci_c (see module docstring for the Tmax->UTCI reprojection),
# then (point, low, high) triples for the 95% CI of relative risk, for
# all-sex/male/female - straight from Sharma et al. 2024 Table 3.
CURVE_POINTS = [
    # utci_c, tmax_source, n_days,  all(pt,lo,hi),        male(pt,lo,hi),        female(pt,lo,hi)
    (28.7, 26.0, 218,    (1.00, 1.00, 1.00),   (1.00, 1.00, 1.00),   (1.00, 1.00, 1.00)),   # MMT
    (42.6, 38.0, 377,    (1.13, 1.10, 1.16),   (1.10, 1.06, 1.14),   (1.18, 1.13, 1.23)),   # P85
    (43.8, 38.9, 409,    (1.19, 1.16, 1.23),   (1.15, 1.11, 1.20),   (1.26, 1.20, 1.32)),   # P90
    (44.4, 39.5, 367,    (1.25, 1.21, 1.29),   (1.20, 1.15, 1.25),   (1.33, 1.26, 1.40)),   # P93
    (44.9, 40.0, 376,    (1.30, 1.26, 1.35),   (1.25, 1.19, 1.30),   (1.40, 1.32, 1.48)),   # P95 / IMD threshold
    (45.8, 40.7, 359,    (1.40, 1.35, 1.45),   (1.33, 1.27, 1.39),   (1.51, 1.43, 1.60)),   # P97
    (46.1, 41.0, 361,    (1.45, 1.40, 1.50),   (1.37, 1.31, 1.44),   (1.57, 1.48, 1.66)),
    (46.9, 41.8, 234,    (1.61, 1.55, 1.68),   (1.52, 1.44, 1.60),   (1.75, 1.64, 1.87)),   # P99
    (47.4, 42.3, 164,    (1.74, 1.66, 1.82),   (1.64, 1.54, 1.75),   (1.89, 1.75, 2.04)),   # P99.5
    (50.4, 45.0, 13,     (3.08, 2.47, 3.83),   (3.03, 2.28, 4.02),   (3.11, 2.20, 4.38)),
]

MAX_OBSERVED_UTCI = CURVE_POINTS[-1][0]

_UTCI_AXIS = np.array([p[0] for p in CURVE_POINTS])

_GENDER_COLUMN = {"all": 3, "male": 4, "female": 5}

_CURVES = {
    gender: {
        "point": np.array([p[col][0] for p in CURVE_POINTS]),
        "low": np.array([p[col][1] for p in CURVE_POINTS]),
        "high": np.array([p[col][2] for p in CURVE_POINTS]),
    }
    for gender, col in _GENDER_COLUMN.items()
}


def _interpolate(utci_c, axis_values):

    if utci_c <= _UTCI_AXIS[0]:
        return 1.0

    if utci_c >= MAX_OBSERVED_UTCI:
        x0, x1 = _UTCI_AXIS[-2], _UTCI_AXIS[-1]
        y0, y1 = axis_values[-2], axis_values[-1]
        slope = (y1 - y0) / (x1 - x0)
        return float(y1 + slope * (utci_c - x1))

    return float(np.interp(utci_c, _UTCI_AXIS, axis_values))


def relative_risk(utci_c, gender="all"):
    """
    Relative risk of all-cause mortality at a given UTCI value, per the
    Sharma et al. 2024 Ahmedabad curve reprojected onto UTCI - point
    estimate plus the paper's own real 95% CI, interpolated the same way.

    Piecewise-linear interpolation between real curve points - no
    invented curvature beyond what the 9 real points support. Below the
    lowest point (MMT), risk is floored at 1.0 (no evidence of excess
    heat mortality below the minimum mortality temperature). Above the
    highest real point, values are a linear extrapolation of the last
    segment - flagged via `is_beyond_observed_range`.

    Parameters
    ----------
    utci_c : float
        Forecast or observed UTCI, degrees Celsius.
    gender : str
        "all", "male", or "female".

    Returns
    -------
    dict with relative_risk (point/low/high), risk_increase_percent
    (point/low/high), and is_beyond_observed_range.
    """

    if gender not in _CURVES:
        raise ValueError(
            f"gender must be one of {list(_CURVES)}, got {gender!r}"
        )

    curve = _CURVES[gender]

    rr_point = _interpolate(utci_c, curve["point"])
    rr_low = _interpolate(utci_c, curve["low"])
    rr_high = _interpolate(utci_c, curve["high"])

    return {
        "relative_risk": rr_point,
        "relative_risk_low": rr_low,
        "relative_risk_high": rr_high,
        "risk_increase_percent": (rr_point - 1.0) * 100.0,
        "risk_increase_percent_low": (rr_low - 1.0) * 100.0,
        "risk_increase_percent_high": (rr_high - 1.0) * 100.0,
        "is_beyond_observed_range": utci_c > MAX_OBSERVED_UTCI,
    }
