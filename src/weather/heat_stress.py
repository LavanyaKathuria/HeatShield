"""
Human thermal stress index calculations.

Combines temperature, humidity, wind, and solar radiation into
Heat Index (HI), shaded Wet-Bulb Globe Temperature (WBGT), and the
Universal Thermal Climate Index (UTCI) - instead of relying on
dry-bulb temperature alone, which is what the standard IMD heatwave
threshold does.

All three formulas below are implemented directly (not imported from a
third-party library) - each is a real, published, closed-form regression
equation, cited at its definition:

- Heat Index: Rothfusz (1990) NWS regression.
- WBGT (shade): Australian Bureau of Meteorology simplified formula.
- UTCI: Broede et al. (2012), "Deriving the operational procedure for
  the Universal Thermal Climate Index (UTCI)", Int J Biometeorol 56:481-94
  - the official ~6th-order rational polynomial approximation to the
  underlying Fiala multi-node thermophysiological model, which is the
  formula every UTCI implementation worldwide uses (it is the published
  algorithm itself, not a black-box library's invention).
"""

import math


STEFAN_BOLTZMANN = 5.670374419e-8  # W/m^2/K^4

# Standing-person average projected area factor and body emissivity,
# used below to estimate mean radiant temperature from global
# horizontal irradiance (ISO 7726-style simplification).
PROJECTED_AREA_FACTOR = 0.25
BODY_EMISSIVITY = 0.97

# UTCI's own valid input ranges (Broede et al. 2012): outside these, the
# polynomial is extrapolating beyond where it was fit.
UTCI_MIN_WIND_MS = 0.5
UTCI_MAX_WIND_MS = 17.0
UTCI_TDB_RANGE = (-50.0, 50.0)
UTCI_TR_MINUS_TDB_RANGE = (-30.0, 70.0)

UTCI_STRESS_CATEGORIES = [
    (-40.0, "extreme cold stress"),
    (-27.0, "very strong cold stress"),
    (-13.0, "strong cold stress"),
    (0.0, "moderate cold stress"),
    (9.0, "slight cold stress"),
    (26.0, "no thermal stress"),
    (32.0, "moderate heat stress"),
    (38.0, "strong heat stress"),
    (46.0, "very strong heat stress"),
]
UTCI_EXTREME_HEAT_LABEL = "extreme heat stress"


def estimate_mean_radiant_temperature(temp_c, solar_radiation_wm2):
    """
    Approximate mean radiant temperature (Tmrt) from global horizontal
    irradiance when no direct/diffuse split or black-globe thermometer
    reading is available.

    This is a simplified radiative-balance estimate (ISO 7726-style):
    it treats the extra radiant heat load on a standing person as a
    fraction (PROJECTED_AREA_FACTOR) of the incoming shortwave flux,
    and solves the equivalent black-body temperature for that load.
    It ignores diffuse/reflected partitioning and solar angle, so it
    is adequate for a first-pass heat-stress screening, not a
    substitute for a full 6-directional radiation measurement.
    """

    temp_k = temp_c + 273.15

    radiant_load = (
        PROJECTED_AREA_FACTOR * max(solar_radiation_wm2, 0.0)
    ) / (BODY_EMISSIVITY * STEFAN_BOLTZMANN)

    mrt_k = (temp_k ** 4 + radiant_load) ** 0.25

    return mrt_k - 273.15


def calculate_wbgt_shade(temp_c, relative_humidity):
    """
    Australian Bureau of Meteorology simplified WBGT (shade)
    approximation. Uses only temperature and humidity - it does not
    include direct solar/wind load, but is already a large
    improvement over dry-bulb temperature alone and is what most
    public heat-health warning systems use as a baseline.
    """

    vapour_pressure = (
        (relative_humidity / 100.0)
        * 6.105
        * math.exp(17.27 * temp_c / (237.7 + temp_c))
    )

    return 0.567 * temp_c + 0.393 * vapour_pressure + 3.94


def calculate_heat_index(temp_c, relative_humidity):
    """
    Rothfusz (1990) NWS regression for apparent temperature ("Heat
    Index"), Celsius-adapted form. Published as valid above ~27C; below
    that the regression is not meaningful and the value is not computed.
    """

    if temp_c < 27.0:
        return None

    return (
        -8.784695
        + 1.61139411 * temp_c
        + 2.338549 * relative_humidity
        - 0.14611605 * temp_c * relative_humidity
        - 1.2308094e-2 * temp_c ** 2
        - 1.6424828e-2 * relative_humidity ** 2
        + 2.211732e-3 * temp_c ** 2 * relative_humidity
        + 7.2546e-4 * temp_c * relative_humidity ** 2
        - 3.582e-6 * temp_c ** 2 * relative_humidity ** 2
    )


def _saturation_vapour_pressure_hpa(temp_c):
    """
    Saturation vapour pressure over water, WMO Goff-Gratch-form
    integration used in the UTCI reference implementation (Broede et al.
    2012). Returns hPa.
    """

    g = [
        -2836.5744,
        -6028.076559,
        19.54263612,
        -0.02737830188,
        0.000016261698,
        7.0229056e-10,
        -1.8680009e-13,
    ]

    temp_k = temp_c + 273.15

    log_es = 2.7150305 * math.log1p(temp_k)

    for power, coefficient in enumerate(g):
        log_es += coefficient * (temp_k ** (power - 2))

    return math.exp(log_es) * 0.01  # Pa -> hPa


def _utci_polynomial(tdb, v, delta_t_tr, pa):
    """
    Broede et al. (2012) 6th-order rational polynomial approximation to
    the Fiala multi-node model's UTCI output, as a function of dry bulb
    temperature (tdb, C), wind speed (v, m/s), mean-radiant-temperature
    offset (delta_t_tr = tr - tdb, C), and water vapour pressure (pa,
    kPa). This is the official published operational formula - every
    UTCI implementation (R, Python, the reference Fortran/VBA code from
    utci.org) uses these exact coefficients, because it IS the
    published algorithm, not a library's own derivation.
    """

    return (
        tdb
        + 0.607562052
        + (-0.0227712343) * tdb
        + (8.06470249e-4) * tdb * tdb
        + (-1.54271372e-4) * tdb ** 3
        + (-3.24651735e-6) * tdb ** 4
        + (7.32602852e-8) * tdb ** 5
        + (1.35959073e-9) * tdb ** 6
        + (-2.25836520) * v
        + 0.0880326035 * tdb * v
        + 0.00216844454 * tdb * tdb * v
        + (-1.53347087e-5) * tdb ** 3 * v
        + (-5.72983704e-7) * tdb ** 4 * v
        + (-2.55090145e-9) * tdb ** 5 * v
        + (-0.751269505) * v * v
        + (-0.00408350271) * tdb * v * v
        + (-5.21670675e-5) * tdb * tdb * v * v
        + (1.94544667e-6) * tdb ** 3 * v * v
        + (1.14099531e-8) * tdb ** 4 * v * v
        + 0.158137256 * v ** 3
        + (-6.57263143e-5) * tdb * v ** 3
        + (2.22697524e-7) * tdb * tdb * v ** 3
        + (-4.16117031e-8) * tdb ** 3 * v ** 3
        + (-0.0127762753) * v ** 4
        + (9.66891875e-6) * tdb * v ** 4
        + (2.52785852e-9) * tdb * tdb * v ** 4
        + (4.56306672e-4) * v ** 5
        + (-1.74202546e-7) * tdb * v ** 5
        + (-5.91491269e-6) * v ** 6
        + 0.398374029 * delta_t_tr
        + (1.83945314e-4) * tdb * delta_t_tr
        + (-1.73754510e-4) * tdb * tdb * delta_t_tr
        + (-7.60781159e-7) * tdb ** 3 * delta_t_tr
        + (3.77830287e-8) * tdb ** 4 * delta_t_tr
        + (5.43079673e-10) * tdb ** 5 * delta_t_tr
        + (-0.0200518269) * v * delta_t_tr
        + (8.92859837e-4) * tdb * v * delta_t_tr
        + (3.45433048e-6) * tdb * tdb * v * delta_t_tr
        + (-3.77925774e-7) * tdb ** 3 * v * delta_t_tr
        + (-1.69699377e-9) * tdb ** 4 * v * delta_t_tr
        + (1.69992415e-4) * v * v * delta_t_tr
        + (-4.99204314e-5) * tdb * v * v * delta_t_tr
        + (2.47417178e-7) * tdb * tdb * v * v * delta_t_tr
        + (1.07596466e-8) * tdb ** 3 * v * v * delta_t_tr
        + (8.49242932e-5) * v ** 3 * delta_t_tr
        + (1.35191328e-6) * tdb * v ** 3 * delta_t_tr
        + (-6.21531254e-9) * tdb * tdb * v ** 3 * delta_t_tr
        + (-4.99410301e-6) * v ** 4 * delta_t_tr
        + (-1.89489258e-8) * tdb * v ** 4 * delta_t_tr
        + (8.15300114e-8) * v ** 5 * delta_t_tr
        + (7.55043090e-4) * delta_t_tr * delta_t_tr
        + (-5.65095215e-5) * tdb * delta_t_tr * delta_t_tr
        + (-4.52166564e-7) * tdb * tdb * delta_t_tr * delta_t_tr
        + (2.46688878e-8) * tdb ** 3 * delta_t_tr * delta_t_tr
        + (2.42674348e-10) * tdb ** 4 * delta_t_tr * delta_t_tr
        + (1.54547250e-4) * v * delta_t_tr * delta_t_tr
        + (5.24110970e-6) * tdb * v * delta_t_tr * delta_t_tr
        + (-8.75874982e-8) * tdb * tdb * v * delta_t_tr * delta_t_tr
        + (-1.50743064e-9) * tdb ** 3 * v * delta_t_tr * delta_t_tr
        + (-1.56236307e-5) * v * v * delta_t_tr * delta_t_tr
        + (-1.33895614e-7) * tdb * v * v * delta_t_tr * delta_t_tr
        + (2.49709824e-9) * tdb * tdb * v * v * delta_t_tr * delta_t_tr
        + (6.51711721e-7) * v ** 3 * delta_t_tr * delta_t_tr
        + (1.94960053e-9) * tdb * v ** 3 * delta_t_tr * delta_t_tr
        + (-1.00361113e-8) * v ** 4 * delta_t_tr * delta_t_tr
        + (-1.21206673e-5) * delta_t_tr ** 3
        + (-2.18203660e-7) * tdb * delta_t_tr ** 3
        + (7.51269482e-9) * tdb * tdb * delta_t_tr ** 3
        + (9.79063848e-11) * tdb ** 3 * delta_t_tr ** 3
        + (1.25006734e-6) * v * delta_t_tr ** 3
        + (-1.81584736e-9) * tdb * v * delta_t_tr ** 3
        + (-3.52197671e-10) * tdb * tdb * v * delta_t_tr ** 3
        + (-3.36514630e-8) * v * v * delta_t_tr ** 3
        + (1.35908359e-10) * tdb * v * v * delta_t_tr ** 3
        + (4.17032620e-10) * v ** 3 * delta_t_tr ** 3
        + (-1.30369025e-9) * delta_t_tr ** 4
        + (4.13908461e-10) * tdb * delta_t_tr ** 4
        + (9.22652254e-12) * tdb * tdb * delta_t_tr ** 4
        + (-5.08220384e-9) * v * delta_t_tr ** 4
        + (-2.24730961e-11) * tdb * v * delta_t_tr ** 4
        + (1.17139133e-10) * v * v * delta_t_tr ** 4
        + (6.62154879e-10) * delta_t_tr ** 5
        + (4.03863260e-13) * tdb * delta_t_tr ** 5
        + (1.95087203e-12) * v * delta_t_tr ** 5
        + (-4.73602469e-12) * delta_t_tr ** 6
        + 5.12733497 * pa
        + (-0.312788561) * tdb * pa
        + (-0.0196701861) * tdb * tdb * pa
        + (9.99690870e-4) * tdb ** 3 * pa
        + (9.51738512e-6) * tdb ** 4 * pa
        + (-4.66426341e-7) * tdb ** 5 * pa
        + 0.548050612 * v * pa
        + (-0.00330552823) * tdb * v * pa
        + (-0.00164119440) * tdb * tdb * v * pa
        + (-5.16670694e-6) * tdb ** 3 * v * pa
        + (9.52692432e-7) * tdb ** 4 * v * pa
        + (-0.0429223622) * v * v * pa
        + 0.00500845667 * tdb * v * v * pa
        + (1.00601257e-6) * tdb * tdb * v * v * pa
        + (-1.81748644e-6) * tdb ** 3 * v * v * pa
        + (-1.25813502e-3) * v ** 3 * pa
        + (-1.79330391e-4) * tdb * v ** 3 * pa
        + (2.34994441e-6) * tdb * tdb * v ** 3 * pa
        + (1.29735808e-4) * v ** 4 * pa
        + (1.29064870e-6) * tdb * v ** 4 * pa
        + (-2.28558686e-6) * v ** 5 * pa
        + (-0.0369476348) * delta_t_tr * pa
        + 0.00162325322 * tdb * delta_t_tr * pa
        + (-3.14279680e-5) * tdb * tdb * delta_t_tr * pa
        + (2.59835559e-6) * tdb ** 3 * delta_t_tr * pa
        + (-4.77136523e-8) * tdb ** 4 * delta_t_tr * pa
        + (8.64203390e-3) * v * delta_t_tr * pa
        + (-6.87405181e-4) * tdb * v * delta_t_tr * pa
        + (-9.13863872e-6) * tdb * tdb * v * delta_t_tr * pa
        + (5.15916806e-7) * tdb ** 3 * v * delta_t_tr * pa
        + (-3.59217476e-5) * v * v * delta_t_tr * pa
        + (3.28696511e-5) * tdb * v * v * delta_t_tr * pa
        + (-7.10542454e-7) * tdb * tdb * v * v * delta_t_tr * pa
        + (-1.24382300e-5) * v ** 3 * delta_t_tr * pa
        + (-7.38584400e-9) * tdb * v ** 3 * delta_t_tr * pa
        + (2.20609296e-7) * v ** 4 * delta_t_tr * pa
        + (-7.32469180e-4) * delta_t_tr * delta_t_tr * pa
        + (-1.87381964e-5) * tdb * delta_t_tr * delta_t_tr * pa
        + (4.80925239e-6) * tdb * tdb * delta_t_tr * delta_t_tr * pa
        + (-8.75492040e-8) * tdb ** 3 * delta_t_tr * delta_t_tr * pa
        + (2.77862930e-5) * v * delta_t_tr * delta_t_tr * pa
        + (-5.06004592e-6) * tdb * v * delta_t_tr * delta_t_tr * pa
        + (1.14325367e-7) * tdb * tdb * v * delta_t_tr * delta_t_tr * pa
        + (2.53016723e-6) * v * v * delta_t_tr * delta_t_tr * pa
        + (-1.72857035e-8) * tdb * v * v * delta_t_tr * delta_t_tr * pa
        + (-3.95079398e-8) * v ** 3 * delta_t_tr * delta_t_tr * pa
        + (-3.59413173e-7) * delta_t_tr ** 3 * pa
        + (7.04388046e-7) * tdb * delta_t_tr ** 3 * pa
        + (-1.89309167e-8) * tdb * tdb * delta_t_tr ** 3 * pa
        + (-4.79768731e-7) * v * delta_t_tr ** 3 * pa
        + (7.96079978e-9) * tdb * v * delta_t_tr ** 3 * pa
        + (1.62897058e-9) * v * v * delta_t_tr ** 3 * pa
        + (3.94367674e-8) * delta_t_tr ** 4 * pa
        + (-1.18566247e-9) * tdb * delta_t_tr ** 4 * pa
        + (3.34678041e-10) * v * delta_t_tr ** 4 * pa
        + (-1.15606447e-10) * delta_t_tr ** 5 * pa
        + (-2.80626406) * pa * pa
        + 0.548712484 * tdb * pa * pa
        + (-0.00399428410) * tdb * tdb * pa * pa
        + (-9.54009191e-4) * tdb ** 3 * pa * pa
        + (1.93090978e-5) * tdb ** 4 * pa * pa
        + (-0.308806365) * v * pa * pa
        + 0.0116952364 * tdb * v * pa * pa
        + (4.95271903e-4) * tdb * tdb * v * pa * pa
        + (-1.90710882e-5) * tdb ** 3 * v * pa * pa
        + 0.00210787756 * v * v * pa * pa
        + (-6.98445738e-4) * tdb * v * v * pa * pa
        + (2.30109073e-5) * tdb * tdb * v * v * pa * pa
        + (4.17856590e-4) * v ** 3 * pa * pa
        + (-1.27043871e-5) * tdb * v ** 3 * pa * pa
        + (-3.04620472e-6) * v ** 4 * pa * pa
        + 0.0514507424 * delta_t_tr * pa * pa
        + (-0.00432510997) * tdb * delta_t_tr * pa * pa
        + (8.99281156e-5) * tdb * tdb * delta_t_tr * pa * pa
        + (-7.14663943e-7) * tdb ** 3 * delta_t_tr * pa * pa
        + (-2.66016305e-4) * v * delta_t_tr * pa * pa
        + (2.63789586e-4) * tdb * v * delta_t_tr * pa * pa
        + (-7.01199003e-6) * tdb * tdb * v * delta_t_tr * pa * pa
        + (-1.06823306e-4) * v * v * delta_t_tr * pa * pa
        + (3.61341136e-6) * tdb * v * v * delta_t_tr * pa * pa
        + (2.29748967e-7) * v ** 3 * delta_t_tr * pa * pa
        + (3.04788893e-4) * delta_t_tr * delta_t_tr * pa * pa
        + (-6.42070836e-5) * tdb * delta_t_tr * delta_t_tr * pa * pa
        + (1.16257971e-6) * tdb * tdb * delta_t_tr * delta_t_tr * pa * pa
        + (7.68023384e-6) * v * delta_t_tr * delta_t_tr * pa * pa
        + (-5.47446896e-7) * tdb * v * delta_t_tr * delta_t_tr * pa * pa
        + (-3.59937910e-8) * v * v * delta_t_tr * delta_t_tr * pa * pa
        + (-4.36497725e-6) * delta_t_tr ** 3 * pa * pa
        + (1.68737969e-7) * tdb * delta_t_tr ** 3 * pa * pa
        + (2.67489271e-8) * v * delta_t_tr ** 3 * pa * pa
        + (3.23926897e-9) * delta_t_tr ** 4 * pa * pa
        + (-0.0353874123) * pa ** 3
        + (-0.221201190) * tdb * pa ** 3
        + 0.0155126038 * tdb * tdb * pa ** 3
        + (-2.63917279e-4) * tdb ** 3 * pa ** 3
        + 0.0453433455 * v * pa ** 3
        + (-0.00432943862) * tdb * v * pa ** 3
        + (1.45389826e-4) * tdb * tdb * v * pa ** 3
        + (2.17508610e-4) * v * v * pa ** 3
        + (-6.66724702e-5) * tdb * v * v * pa ** 3
        + (3.33217140e-5) * v ** 3 * pa ** 3
        + (-0.00226921615) * delta_t_tr * pa ** 3
        + (3.80261982e-4) * tdb * delta_t_tr * pa ** 3
        + (-5.45314314e-9) * tdb * tdb * delta_t_tr * pa ** 3
        + (-7.96355448e-4) * v * delta_t_tr * pa ** 3
        + (2.53458034e-5) * tdb * v * delta_t_tr * pa ** 3
        + (-6.31223658e-6) * v * v * delta_t_tr * pa ** 3
        + (3.02122035e-4) * delta_t_tr * delta_t_tr * pa ** 3
        + (-4.77403547e-6) * tdb * delta_t_tr * delta_t_tr * pa ** 3
        + (1.73825715e-6) * v * delta_t_tr * delta_t_tr * pa ** 3
        + (-4.09087898e-7) * delta_t_tr ** 3 * pa ** 3
        + 0.614155345 * pa ** 4
        + (-0.0616755931) * tdb * pa ** 4
        + 0.00133374846 * tdb * tdb * pa ** 4
        + 0.00355375387 * v * pa ** 4
        + (-5.13027851e-4) * tdb * v * pa ** 4
        + (1.02449757e-4) * v * v * pa ** 4
        + (-0.00148526421) * delta_t_tr * pa ** 4
        + (-4.11469183e-5) * tdb * delta_t_tr * pa ** 4
        + (-6.80434415e-6) * v * delta_t_tr * pa ** 4
        + (-9.77675906e-6) * delta_t_tr * delta_t_tr * pa ** 4
        + 0.0882773108 * pa ** 5
        + (-0.00301859306) * tdb * pa ** 5
        + 0.00104452989 * v * pa ** 5
        + (2.47090539e-4) * delta_t_tr * pa ** 5
        + 0.00148348065 * pa ** 6
    )


def _utci_stress_category(utci_c):
    """
    Each (threshold, category) pair means "this category's range ends
    at threshold" (upper-bound inclusive) - e.g. (46.0, "very strong
    heat stress") covers (38, 46]. This matches the official UTCI
    category definitions exactly. Anything above the highest threshold
    (46.0) falls through to UTCI_EXTREME_HEAT_LABEL.

    An earlier version of this function used the opposite convention
    (largest threshold <= value), which silently mislabeled most
    non-boundary values one category too low, and made "extreme heat
    stress" unreachable for any finite input - caught by cross-checking
    against pythermalcomfort's reference mapping() function across many
    values, not just exact boundaries.
    """

    for threshold, category in UTCI_STRESS_CATEGORIES:
        if utci_c <= threshold:
            return category

    return UTCI_EXTREME_HEAT_LABEL


def calculate_utci(temp_c, mean_radiant_temp_c, wind_speed_ms, relative_humidity):
    """
    Universal Thermal Climate Index - Broede et al. (2012) official
    polynomial (see module docstring). Wind is clipped to the model's
    valid range (0.5-17 m/s); dry-bulb and radiant-offset are checked
    against their valid ranges and flagged (not silently dropped) if
    exceeded, matching how the rest of this codebase treats
    out-of-range extrapolation (see dose_response.py).
    """

    clipped_wind_ms = min(
        max(wind_speed_ms, UTCI_MIN_WIND_MS), UTCI_MAX_WIND_MS
    )

    delta_t_tr = mean_radiant_temp_c - temp_c

    saturation_vapour_pressure_hpa = _saturation_vapour_pressure_hpa(temp_c)
    vapour_pressure_hpa = (
        saturation_vapour_pressure_hpa * (relative_humidity / 100.0)
    )
    vapour_pressure_kpa = vapour_pressure_hpa / 10.0

    utci_c = _utci_polynomial(
        tdb=temp_c,
        v=clipped_wind_ms,
        delta_t_tr=delta_t_tr,
        pa=vapour_pressure_kpa,
    )

    within_valid_range = (
        UTCI_TDB_RANGE[0] <= temp_c <= UTCI_TDB_RANGE[1]
        and UTCI_TR_MINUS_TDB_RANGE[0] <= delta_t_tr <= UTCI_TR_MINUS_TDB_RANGE[1]
    )

    return {
        "utci_c": round(utci_c, 1),
        "utci_stress_category": _utci_stress_category(utci_c),
        "utci_beyond_valid_input_range": not within_valid_range,
    }


def calculate_heat_stress(
    temp_c,
    relative_humidity,
    wind_speed_ms,
    solar_radiation_wm2
):
    """
    Compute Heat Index, shaded WBGT, and UTCI for one
    temperature/humidity/wind/radiation reading.
    """

    heat_index_c = calculate_heat_index(temp_c, relative_humidity)

    wbgt_shade_c = calculate_wbgt_shade(
        temp_c, relative_humidity
    )

    mean_radiant_temp_c = estimate_mean_radiant_temperature(
        temp_c, solar_radiation_wm2
    )

    utci_result = calculate_utci(
        temp_c=temp_c,
        mean_radiant_temp_c=mean_radiant_temp_c,
        wind_speed_ms=wind_speed_ms,
        relative_humidity=relative_humidity,
    )

    return {
        "heat_index_c": heat_index_c,
        "wbgt_shade_c": round(wbgt_shade_c, 2),
        "mean_radiant_temp_c": round(mean_radiant_temp_c, 2),
        "utci_c": utci_result["utci_c"],
        "utci_stress_category": utci_result["utci_stress_category"],
        "utci_beyond_valid_input_range":
            utci_result["utci_beyond_valid_input_range"],
    }
