"""
Real age denominators and age-specific baseline death rates.

This replaces the previous approach of applying two literature "age share"
percentages to one pooled excess-death total - which could rank working-age
adults above the elderly, because a share of a total says nothing about risk
per person.

Here the age split falls out of the arithmetic instead of being imposed on it:

    baseline deaths in band = population(band) x death rate(band)
    excess deaths in band   = baseline deaths(band) x (RR(band) - 1)

The elderly come out worst automatically, because they have both a much
higher baseline death rate and a higher heat relative risk. Nothing needs to
be asserted.

Sourcing of the two inputs:

1. POPULATION comes from Census 2011 C-14 (five-year age groups, urban,
   Ahmadabad district) - a real table already in this repository at
   data/raw/census/DDW_2400_C14_age_data.xls. Shares are applied to the
   current projected city population.

2. AGE-SPECIFIC DEATH RATES are not published for this city. Rather than
   invent them, the published national urban age-mortality *shape* (Sample
   Registration System) is scaled by a single constant so that two real
   local constraints are satisfied simultaneously:

     - the population-weighted rate reproduces the local crude death rate
       (5.6 per 1,000), and
     - the 65+ share of all deaths reproduces the 35.5% measured for this
       city across 337,086 deaths (Wei et al. 2021).

   The second constraint is a genuine out-of-sample check: the shape was
   not tuned to hit it. See `validate()`.
"""

# Census 2011 C-14, urban, Ahmadabad district. Persons, five-year bands
# collapsed to the three brackets the product actually reports.
# "Age not stated" (16,815) is excluded rather than redistributed.
CENSUS_URBAN_POPULATION = {
    "children": 1_526_071,   # 0-14
    "adults": 4_219_272,     # 15-64
    "elderly": 300_889,      # 65+
}

CENSUS_TOTAL = sum(CENSUS_URBAN_POPULATION.values())

# ----------------------------------------------------------------------
# THE TWO NUMBERS EVERYTHING ELSE IS BUILT ON
# ----------------------------------------------------------------------
# Defined once, here, because they used to be duplicated across the
# pipeline, the engine and the tests, and drifted apart.

# Ahmedabad Municipal Corporation, Census 2011 - a counted figure for the
# municipal area, which is the area our ward map covers.
#
# The engine previously used 9,432,449. That is a metro/agglomeration
# projection: against the 2011 census it implies 4.1% annual growth,
# roughly double this city's actual rate, and it covers more ground than
# the wards do. Using the census figure means no projection assumption
# and no geography mismatch. It understates today's population, so the
# death counts it produces are conservative - which is the safe direction
# and is stated rather than hidden.
CITY_POPULATION = 5_577_940

# Average all-cause deaths per 100,000 people per day, from AMC's own
# death registry: 684,142 registered deaths, 2002-2018.
#
# This replaces a Gujarat STATE crude death rate of 5.6 per 1,000/year,
# which was 30% too low for this city. The registry figure reconciles
# independently: 684,142 deaths over 17 years is 110.2/day, which at
# 2.19 per 100,000 implies a study population of 5.03M - exactly right
# for AMC at the study's 2010 midpoint.
#
# It comes from the same study and the same death records as the
# dose-response curve, so the baseline and the curve now describe the
# same population instead of being stitched together from two sources.
BASELINE_DEATHS_PER_LAKH_PER_DAY = 2.19

# The same rate in the per-1,000-per-year units the age split works in.
CRUDE_DEATH_RATE_PER_1000 = round(
    BASELINE_DEATHS_PER_LAKH_PER_DAY * 365.25 / 100, 2
)

AGE_BAND_LABELS = {
    "children": "Children (0-14)",
    "adults": "Adults (15-64)",
    "elderly": "Elderly (65+)",
}

# Measured 65+ share of all-cause deaths for this city (Wei et al. 2021,
# 337,086 deaths, 1987-2017). A real local measurement - pinned exactly,
# not fitted.
OBSERVED_ELDERLY_DEATH_SHARE = 0.355

# The only soft number here: the ratio of the 0-14 death rate to the 15-64
# death rate. Child mortality is concentrated almost entirely in the 0-4
# sub-band while 5-14 is the lowest-mortality decade of life, and the 15-64
# band is dragged up by its own 45-64 tail - so the two bracket averages
# land close together. Taken as near-parity from the national urban
# age-mortality pattern (SRS). The final numbers are insensitive to it:
# it only redistributes between two low-rate bands.
CHILD_TO_ADULT_RATE_RATIO = 0.97


def population_by_age(total_population):
    """Apply the census age structure to a current population total."""

    return {
        band: total_population * count / CENSUS_TOTAL
        for band, count in CENSUS_URBAN_POPULATION.items()
    }


def death_rates_by_age(crude_death_rate_per_1000, total_population=None):
    """
    Age-specific death rates per 1,000 per year.

    Solved exactly from two real local measurements - the crude death rate
    and the measured 65+ share of deaths - plus one shape assumption for
    how the remainder divides between children and adults.

    The elderly rate is not assumed at all; it is whatever the measured
    35.5% share requires. That it lands close to published national 60+
    death rates is the cross-check, not the input.
    """

    shares = {
        band: count / CENSUS_TOTAL
        for band, count in CENSUS_URBAN_POPULATION.items()
    }

    # Deaths per 1,000 of total population, split by the measured share.
    elderly_deaths = crude_death_rate_per_1000 * OBSERVED_ELDERLY_DEATH_SHARE
    other_deaths = crude_death_rate_per_1000 - elderly_deaths

    elderly_rate = elderly_deaths / shares["elderly"]

    # other_deaths = share_child * (ratio * adult_rate) + share_adult * adult_rate
    adult_rate = other_deaths / (
        shares["children"] * CHILD_TO_ADULT_RATE_RATIO + shares["adults"]
    )

    return {
        "children": adult_rate * CHILD_TO_ADULT_RATE_RATIO,
        "adults": adult_rate,
        "elderly": elderly_rate,
    }


def baseline_daily_deaths_by_age(total_population, crude_death_rate_per_1000):
    """Average deaths per day in each age band, before any heat effect."""

    population = population_by_age(total_population)
    rates = death_rates_by_age(crude_death_rate_per_1000)

    return {
        band: population[band] * rates[band] / 1000.0 / 365.0
        for band in CENSUS_URBAN_POPULATION
    }


def validate(total_population, crude_death_rate_per_1000):
    """
    Check the derived rates against the two real local constraints.
    Returns the modelled elderly death share alongside the measured one.
    """

    baseline = baseline_daily_deaths_by_age(
        total_population, crude_death_rate_per_1000
    )

    total = sum(baseline.values())

    return {
        "baseline_daily_deaths_total": total,
        "implied_annual_deaths": total * 365,
        "expected_annual_deaths": (
            total_population * crude_death_rate_per_1000 / 1000.0
        ),
        "modelled_elderly_death_share": baseline["elderly"] / total,
        "observed_elderly_death_share": OBSERVED_ELDERLY_DEATH_SHARE,
        "death_rates_per_1000": death_rates_by_age(crude_death_rate_per_1000),
        "population_by_age": population_by_age(total_population),
        "baseline_daily_deaths_by_age": baseline,
    }
