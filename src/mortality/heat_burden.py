"""
Age- and occupation-stratified heat health burden, assembled from every
source available rather than read off one curve.

THE CENTRAL IDEA: TWO MEDICAL PATHWAYS, NOT ONE
-----------------------------------------------
Heat kills in two clinically distinct ways, and the literature disagrees
about who dies only because different studies measure different pathways:

  PATHWAY A - DIRECT heat illness. Heat stroke, heat exhaustion, severe
    dehydration. Acute, diagnosable, recorded by name in hospital
    registers. Skews towards people who are *exposed* - outdoor workers,
    working-age men. Small absolute counts.

  PATHWAY B - INDIRECT all-cause excess. Heat destabilises existing
    cardiovascular, respiratory and renal disease. Nobody is admitted for
    "heat"; the death certificate says heart failure. Skews towards people
    who are *frail* - the elderly. An order of magnitude larger, and only
    visible statistically.

The previous engine collapsed these together: it took the age shares from
a heatstroke study (Pathway A, working-age skew) and applied them to an
all-cause total (Pathway B). That category error is precisely why
working-age adults came out ranking above the elderly. They are kept
strictly apart here.

WHERE EVERY NUMBER COMES FROM
-----------------------------
Nothing here is a single lookup, because no single source covers this.

  Thermal stress          physics + published indices (UTCI/WBGT/HI)
  What counts as heat     30-year local climatology, this repository
  Event severity          Excess Heat Factor, Australian BOM method
  Dose-response shape     Sharma et al. 2024 DLNM curve
  Attributable fraction   Gasparrini & Leone 2014 (1 - 1/RR)
  Age denominators        Census C-14, five-year bands
  Baseline death rates    solved from local crude death rate + measured
                          elderly death share (Wei et al. 2021)
  Pathway A age profile   DERIVED: Guin et al. heatstroke death shares
                          divided by census population shares
  Pathway B age profile   DERIVED: the baseline death rates above
  Worker denominators     Census Primary Census Abstract + labour survey
  Occupational risk       Venugopal et al. 2021, AOR 2.1
  Absolute scale          Dutta et al. recorded municipal case/death counts
  Validation              Azhar et al. 2014 measured 2010 excess

ON HONESTY
----------
The age profiles are now derived rather than assumed. Two soft numbers
remain, both isolated and named so they can be argued with:
`OUTDOOR_SHARE_OF_OTHER_WORKERS` in worker_structure.py, and
`CHILD_TO_ADULT_RATE_RATIO` in age_structure.py.
"""

from . import age_structure
from . import risk_axes
from . import worker_structure
from .dose_response import relative_risk
from ..weather.climatology import NIGHT_ANOMALY_WEIGHT

# Guin, Bhan & Sethi 2025 - share of heatstroke-CLASSIFIED deaths by age,
# India-wide NCRB panel 2001-2019. Shares of deaths, NOT risk: dividing by
# population share is what turns them into risk.
HEATSTROKE_DEATH_SHARE = {
    "under_30": 0.13,
    "30_59": 0.59,
    "60_plus": 0.28,
}

# Census five-year bands making up each of the above, and each of the
# three bands this product reports. Used to translate one banding onto
# the other by population weight.
GUIN_BANDS = {
    "under_30": ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29"],
    "30_59": ["30-34", "35-39", "40-44", "45-49", "50-54", "55-59"],
    "60_plus": ["60-64", "65-69", "70-74", "75-79", "80+"],
}

PRODUCT_BANDS = {
    "children": ["0-4", "5-9", "10-14"],
    "adults": ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
               "45-49", "50-54", "55-59", "60-64"],
    "elderly": ["65-69", "70-74", "75-79", "80+"],
}

# Census C-14 urban five-year populations, Ahmadabad district.
CENSUS_FIVE_YEAR = {
    "0-4": 476696, "5-9": 506559, "10-14": 542816, "15-19": 562553,
    "20-24": 606566, "25-29": 585886, "30-34": 519036, "35-39": 460536,
    "40-44": 406267, "45-49": 363937, "50-54": 302030, "55-59": 232370,
    "60-64": 180091, "65-69": 116231, "70-74": 84302, "75-79": 46244,
    "80+": 54112,
}

# Hospital cases per recorded heat death, from real municipal records
# (274/65, 57/11, 23/8, 99/15, 33/2, 26/3 across 2010 and 2014-2018).
CASES_PER_RECORDED_DEATH = 4.9

# Recorded heat deaths per unit of accumulated Excess Heat Factor, fitted
# through the origin on those same records. Through the origin is what
# forces an ordinary day to zero.
#
# Refitted after the event detector was changed from a flat annual
# significance threshold to a seasonal one. The old coefficient (0.126)
# was fitted against EHF values the system no longer produces and was
# wrong by a factor of eight once the detector was corrected.
#
# The refit is also a check on that correction: against the same six
# years of recorded municipal deaths, R2 went from 0.72 to 0.949. The
# seasonal detector tracks what was actually recorded far better than the
# annual one did.
#
#   2010  modelled 64.1  recorded 65     2016  modelled 14.5  recorded 15
#   2017  modelled  2.5  recorded  2     2015  modelled 13.4  recorded  8
#   2014  modelled  0.7  recorded 11     2018  modelled  0.3  recorded  3
#
# 2014 and 2018 remain badly wrong. Six years of small, administratively
# driven counts cannot support more confidence than that, which is why
# this figure produces a "recorded-equivalent" estimate and never a
# forecast.
RECORDED_DEATHS_PER_EHF_UNIT = 1.0672


def derive_direct_pathway_profile():
    """
    Per-capita relative risk of DIRECT heat illness by age band.

    Derived, not assumed: national heatstroke death shares divided by
    local population shares, then re-weighted from the source study's age
    bands onto the three bands this product reports.

    This is the step the previous engine skipped. Working-age adults hold
    59% of heatstroke deaths, but they are also 38% of the population -
    while the 60+ band holds 28% of deaths on 8% of the population. On a
    per-person basis the elderly are worse off even in the pathway that
    supposedly favours the young.
    """

    total_population = sum(CENSUS_FIVE_YEAR.values())

    # Step 1: per-capita risk within the source study's own age bands.
    per_capita = {}
    for band, ages in GUIN_BANDS.items():
        population_share = (
            sum(CENSUS_FIVE_YEAR[a] for a in ages) / total_population
        )
        per_capita[band] = HEATSTROKE_DEATH_SHARE[band] / population_share

    # Step 2: attach each five-year band to its source-study risk.
    risk_by_five_year = {
        age: per_capita[band]
        for band, ages in GUIN_BANDS.items()
        for age in ages
    }

    # Step 3: population-weight onto this product's bands.
    profile = {}
    for band, ages in PRODUCT_BANDS.items():
        population = sum(CENSUS_FIVE_YEAR[a] for a in ages)
        profile[band] = sum(
            CENSUS_FIVE_YEAR[a] * risk_by_five_year[a] for a in ages
        ) / population

    # Express relative to working-age adults.
    reference = profile["adults"]

    return {band: value / reference for band, value in profile.items()}


DIRECT_PATHWAY_PROFILE = derive_direct_pathway_profile()


def attributable_fraction(utci_c):
    """
    Share of deaths attributable to heat at this thermal stress level.

    `1 - 1/RR`, not `RR - 1`. For a cumulative-lag dose-response curve the
    attributable fraction is the former (Gasparrini & Leone 2014, BMC Med
    Res Methodol 14:55). The difference is not cosmetic: at RR 3.08 the
    wrong form overstates the burden threefold.
    """

    risk = relative_risk(utci_c)

    return {
        "point": 1.0 - 1.0 / risk["relative_risk"],
        "low": 1.0 - 1.0 / risk["relative_risk_low"],
        "high": 1.0 - 1.0 / risk["relative_risk_high"],
        "relative_risk": risk["relative_risk"],
        "is_beyond_observed_range": risk["is_beyond_observed_range"],
    }


class HeatBurdenEngine:

    def __init__(self, population=None, crude_death_rate_per_1000=None):

        # Both default to the single definitions in age_structure, so a
        # caller cannot silently supply a different population or death
        # rate than the rest of the system is using.
        population = (
            age_structure.CITY_POPULATION if population is None else population
        )
        crude_death_rate_per_1000 = (
            age_structure.CRUDE_DEATH_RATE_PER_1000
            if crude_death_rate_per_1000 is None
            else crude_death_rate_per_1000
        )

        self.population = population
        self.crude_death_rate = crude_death_rate_per_1000

        self.population_by_age = age_structure.population_by_age(population)
        self.baseline_by_age = age_structure.baseline_daily_deaths_by_age(
            population, crude_death_rate_per_1000
        )
        self.baseline_total = sum(self.baseline_by_age.values())

        self.outdoor_workers = worker_structure.scaled_outdoor_workers(
            population
        )
        self.outdoor_fraction_of_adults = (
            self.outdoor_workers / self.population_by_age["adults"]
        )

        # AGE AXIS - physiology at equal exposure. Deliberately NOT built
        # from the heatstroke registers, which carry an occupational
        # confound; see risk_axes.py.
        self.age_susceptibility = risk_axes.age_susceptibility({
            band: value / self.baseline_total
            for band, value in self.baseline_by_age.items()
        })

        # OCCUPATION AXIS - exposure at equal physiology. Worker
        # population and its own baseline death rate, independent of the
        # age split above.
        worker_breakdown = worker_structure.worker_breakdown()
        self.all_workers = round(
            population * worker_breakdown["worker_share_of_population"]
        )
        self.worker_death_rate_per_day = (
            age_structure.death_rates_by_age(crude_death_rate_per_1000)
            ["adults"] / 1000.0 / 365.0
        )

        self.direct_profile = DIRECT_PATHWAY_PROFILE

    # ------------------------------------------------------------------
    # Pathway B - indirect, all-cause
    # ------------------------------------------------------------------

    def indirect_burden(self, utci_c, utci_normal_c, is_heat_event=True):
        """
        Excess all-cause deaths from cardiovascular, respiratory and renal
        decompensation, measured against the local seasonal normal.

        `is_heat_event` gates the whole figure. This is a consistency
        rule, not a modelling choice: the burden and the alert must not
        be allowed to disagree. Previously they used different tests -
        the burden measured against the seasonal normal while the event
        detector measured against an annual percentile - and the result
        was a screen reading "nobody is at elevated risk" directly above
        "21 additional deaths". Whatever the model believes, a system
        that contradicts itself in two adjacent lines cannot be trusted
        by the person reading it.
        """

        if not is_heat_event:
            return self._zero_burden()

        today = attributable_fraction(utci_c)
        normal = attributable_fraction(utci_normal_c)

        delta = max(0.0, today["point"] - normal["point"])

        bounds = sorted([
            max(0.0, today["low"] - normal["low"]),
            max(0.0, today["high"] - normal["high"]),
        ])

        by_age = {}
        for band, baseline in self.baseline_by_age.items():
            people = self.population_by_age[band]
            susceptibility = self.age_susceptibility[band]
            deaths = baseline * delta * susceptibility
            by_age[band] = {
                "label": age_structure.AGE_BAND_LABELS[band],
                "population": round(people),
                "susceptibility": round(susceptibility, 3),
                "excess_deaths": round(deaths, 2),
                "excess_deaths_low": round(
                    baseline * bounds[0] * susceptibility, 2
                ),
                "excess_deaths_high": round(
                    baseline * bounds[1] * susceptibility, 2
                ),
                "excess_per_100k": round(deaths / people * 100_000, 4),
            }

        occupational = risk_axes.occupational_split(
            worker_population=self.all_workers,
            outdoor_workers=self.outdoor_workers,
            baseline_death_rate_per_worker=self.worker_death_rate_per_day,
            attributable_fraction=delta,
        )

        return {
            "attributable_fraction": round(delta, 5),
            "total": round(sum(v["excess_deaths"] for v in by_age.values()), 2),
            "total_low": round(
                sum(v["excess_deaths_low"] for v in by_age.values()), 2
            ),
            "total_high": round(
                sum(v["excess_deaths_high"] for v in by_age.values()), 2
            ),
            "by_age": by_age,
            # Reported ALONGSIDE the age bands, not inside them. These
            # workers are already counted in the adult band above; this
            # is the same people viewed on the exposure axis instead of
            # the physiology axis, so the two must never be added.
            "by_occupation": occupational,
            "is_beyond_observed_range": today["is_beyond_observed_range"],
        }

    def _zero_burden(self):
        """The shape of no burden, so callers need no special case."""

        by_age = {}
        for band in self.baseline_by_age:
            by_age[band] = {
                "label": age_structure.AGE_BAND_LABELS[band],
                "population": round(self.population_by_age[band]),
                "susceptibility": round(self.age_susceptibility[band], 3),
                "excess_deaths": 0.0,
                "excess_deaths_low": 0.0,
                "excess_deaths_high": 0.0,
                "excess_per_100k": 0.0,
            }

        return {
            "attributable_fraction": 0.0,
            "total": 0.0,
            "total_low": 0.0,
            "total_high": 0.0,
            "by_age": by_age,
            "by_occupation": None,
            "is_beyond_observed_range": False,
        }

    # ------------------------------------------------------------------
    # Pathway A - direct heat illness
    # ------------------------------------------------------------------

    def direct_burden(self, ehf):
        """
        Recorded-equivalent heat illness: the cases and deaths a hospital
        would actually log by name.

        Scale comes from real municipal records; the age split comes from
        the derived per-capita heatstroke profile; the occupational split
        uses the measured outdoor/indoor odds ratio.
        """

        if ehf is None or ehf <= 0:
            return None

        deaths = ehf * RECORDED_DEATHS_PER_EHF_UNIT
        cases = deaths * CASES_PER_RECORDED_DEATH

        # Distribute by population x per-capita risk.
        weights = {
            band: self.population_by_age[band] * self.direct_profile[band]
            for band in self.direct_profile
        }
        weight_total = sum(weights.values())

        by_age = {}
        for band, weight in weights.items():
            people = self.population_by_age[band]
            band_deaths = deaths * weight / weight_total
            by_age[band] = {
                "label": age_structure.AGE_BAND_LABELS[band],
                "population": round(people),
                "heat_deaths": round(band_deaths, 2),
                "hospital_cases": round(
                    cases * weight / weight_total, 1
                ),
                "per_100k": round(band_deaths / people * 100_000, 4),
                "relative_risk_per_person": round(
                    self.direct_profile[band], 3
                ),
            }

        return {
            "heat_deaths": round(deaths, 1),
            "hospital_cases": round(cases, 1),
            "by_age": by_age,
        }

    # ------------------------------------------------------------------

    def daily_burden(self, utci_c, utci_normal_c, ehf=None,
                     night_temp_c=None, night_normal_c=None):
        """
        Both pathways for one day in one place, kept separate.

        When overnight readings are supplied, the share of night heat
        above the local normal night is added to the daytime index: a hot
        night denies the body its recovery window, and the daytime peak
        alone cannot see that. Omitting them degrades to a daytime-only
        estimate rather than failing.
        """

        effective_utci = utci_c
        night_anomaly = None

        if night_temp_c is not None and night_normal_c is not None:
            night_anomaly = max(0.0, night_temp_c - night_normal_c)
            effective_utci = utci_c + NIGHT_ANOMALY_WEIGHT * night_anomaly

        # One test decides both halves, so they cannot disagree.
        #
        # A KNOWN non-event suppresses the burden. An UNKNOWN one does
        # not: if the event calculation was unavailable, suppressing
        # would turn a data-fetch failure into silence during a possible
        # heatwave. Unknown falls through to the anomaly, which is always
        # available, and is flagged so the caller can say so.
        event_known = ehf is not None
        is_heat_event = (ehf > 0) if event_known else True

        indirect = self.indirect_burden(
            effective_utci, utci_normal_c, is_heat_event=is_heat_event
        )
        direct = self.direct_burden(ehf)

        return {
            "utci_c": utci_c,
            "effective_utci_c": round(effective_utci, 1),
            "night_anomaly_c": (
                None if night_anomaly is None else round(night_anomaly, 1)
            ),
            "utci_normal_c": round(utci_normal_c, 1),
            "utci_anomaly_c": round(utci_c - utci_normal_c, 1),
            "ehf": None if ehf is None else round(ehf, 1),
            "is_heat_event": is_heat_event,
            # False means the event test could not be run, so the burden
            # below is an anomaly-only estimate that has NOT been gated.
            "event_known": event_known,
            "indirect_all_cause": indirect,
            "direct_heat_illness": direct,
            "highest_risk_group": self._highest_risk_group(indirect, direct),
        }

    def _highest_risk_group(self, indirect, direct):
        """
        Who is worst off per person, across both pathways.

        Per 100,000 of that group - never a share of a pooled total, which
        is what let the largest group masquerade as the most at risk.
        Returns None when there is no excess at all: on an ordinary day
        nobody is most at risk, and naming someone anyway is a false alarm.
        """

        candidates = {
            band: value["excess_per_100k"]
            for band, value in indirect["by_age"].items()
        }

        if direct:
            for band, value in direct["by_age"].items():
                candidates[band] = candidates.get(band, 0) + value["per_100k"]

        if indirect["by_occupation"]:
            candidates["outdoor_workers"] = (
                indirect["by_occupation"]["outdoor_per_100k"]
            )

        highest = max(candidates, key=candidates.get)

        return None if candidates[highest] <= 0 else highest
