"""
The two risk axes, kept deliberately independent.

WHY TWO AXES AND NOT A TREE
---------------------------
Age and occupation answer different questions, and nesting one inside the
other corrupts both:

  AGE AXIS - children / adults / elderly, all assumed to be in the SAME
    PLACE under the SAME heat. This isolates physiology: how well does a
    body of this age cope with identical exposure? It must not be
    computed from occupation.

  OCCUPATION AXIS - outdoor vs indoor workers. This isolates exposure:
    the same adult body, more hours in the sun. It is reported alongside
    the age bands, never as a subdivision of them.

An earlier version derived the age profile from national heatstroke
death records. That was wrong, and the literature shows exactly why.

THE CONFOUND, DOCUMENTED IN THE LITERATURE
------------------------------------------
Studies disagree about whether the elderly or working-age adults are more
at risk from heat, and the disagreement tracks study setting:

  - Rural western India (Vadu HDSS): relative risk HIGHER in men and in
    ages 12-59 than in women and the elderly. The authors attribute this
    directly to agricultural and industrial outdoor work.
  - National heatstroke registers (Guin et al. 2025): 59% of
    heatstroke-classified deaths in ages 30-59, explicitly attributed by
    the authors to outdoor livelihood exposure.
  - Urban Europe (Masselot et al. 2023, 854 cities): risk rises
    monotonically with age, curves "becoming steeper as age increases",
    highest RR 1.60 in the 85+ band.

The first two are measuring occupational exposure and reporting it as an
age effect. The third, in settings without mass outdoor agricultural
labour, recovers the physiological gradient. So the age axis is built
from the physiological evidence, and the occupational evidence is moved
to where it belongs - the occupation axis.

Guin et al. is therefore no longer an input to the age profile. It is
kept as a cross-check on the OCCUPATION axis, which is what it actually
measures.
"""

# ----------------------------------------------------------------------
# AGE AXIS - physiological susceptibility at equal exposure
# ----------------------------------------------------------------------

# Relative risk of the 65+ band against the population average, at the
# same exposure. Indian urban evidence (Chandigarh time-series) reports
# roughly 1.5x for over-65s versus the general population, consistent in
# direction and magnitude with the European multi-city finding that the
# exposure-response curve steepens monotonically with age.
#
# CAVEAT, STATED RATHER THAN BURIED: this is read as a relative risk
# (a multiplier on that band's own baseline mortality). If the source
# instead reports an absolute heat-death rate, applying it on top of an
# age-specific baseline would double-count the frailty effect. Verify
# against the source table before this figure is used in anything
# published.
ELDERLY_RELATIVE_SUSCEPTIBILITY = 1.5

# No source separates children from working-age adults for the indirect
# pathway at equal exposure - European studies begin at age 20, and
# Indian studies do not stratify below 30. Rather than invent a gradient,
# the two are treated alike and the uncertainty is declared. Note this is
# about the INDIRECT pathway; the acute paediatric pathway is real and
# separately evidenced (heat-related neonatal admissions rise sharply
# above 42C) but concerns admissions, not deaths.
CHILD_EQUALS_ADULT_SUSCEPTIBILITY = True


def age_susceptibility(baseline_death_share_by_band):
    """
    Per-band physiological susceptibility multipliers, normalised so the
    death-weighted average is exactly 1.

    Normalising this way guarantees the age split redistributes the
    all-age burden without inventing or losing any of it - the bands
    always sum back to the total.

    Parameters
    ----------
    baseline_death_share_by_band : dict
        Each band's share of baseline daily deaths. Must sum to 1.
    """

    shares = baseline_death_share_by_band

    elderly = ELDERLY_RELATIVE_SUSCEPTIBILITY

    # Solve the remaining mass so the weighted average is 1.
    remaining_weight = shares["children"] + shares["adults"]
    remaining_mass = 1.0 - shares["elderly"] * elderly

    if remaining_weight <= 0:
        raise ValueError("children and adults carry no baseline deaths")

    others = remaining_mass / remaining_weight

    if others <= 0:
        raise ValueError(
            "elderly susceptibility too high for this age structure - "
            "it would leave negative risk for everyone else"
        )

    return {
        "children": others,
        "adults": others,
        "elderly": elderly,
    }


# ----------------------------------------------------------------------
# OCCUPATION AXIS - exposure difference, same physiology
# ----------------------------------------------------------------------

# Outdoor vs indoor workers, adjusted odds ratio for heat-illness
# symptoms: Venugopal et al. 2021, N=2,104 Indian workers, AOR 2.1
# (95% CI 1.60-2.77), adjusted for workload, literacy and age. Adjusting
# for age is what makes this usable as a clean exposure contrast.
OUTDOOR_ODDS_RATIO = 2.1
OUTDOOR_ODDS_RATIO_CI = (1.60, 2.77)

# Cross-check, not an input: Guin et al. 2025 found 79% of
# heatstroke-classified deaths nationally were male and 59% were in ages
# 30-59, attributed by the authors to outdoor work. That is the same
# signal this axis carries, measured a different way.


def occupational_split(worker_population, outdoor_workers,
                       baseline_death_rate_per_worker, attributable_fraction):
    """
    Excess deaths among outdoor and indoor workers at the same heat.

    Both groups are adults with the same physiology, so the age axis is
    held constant here. The only thing that differs is exposure.

    The two rates are solved so that they preserve the worker-population
    total while respecting the odds ratio - rather than simply
    multiplying the outdoor group by 2.1, which would manufacture burden
    that does not exist.
    """

    if worker_population <= 0 or outdoor_workers <= 0:
        return None

    indoor_workers = worker_population - outdoor_workers
    outdoor_fraction = outdoor_workers / worker_population

    total_excess = (
        worker_population * baseline_death_rate_per_worker
        * attributable_fraction
    )

    denominator = (
        (1 - outdoor_fraction) + outdoor_fraction * OUTDOOR_ODDS_RATIO
    )

    outdoor_excess = total_excess * (
        outdoor_fraction * OUTDOOR_ODDS_RATIO / denominator
    )
    indoor_excess = total_excess - outdoor_excess

    return {
        "outdoor_workers": outdoor_workers,
        "indoor_workers": indoor_workers,
        "outdoor_excess_deaths": outdoor_excess,
        "indoor_excess_deaths": indoor_excess,
        "outdoor_per_100k": (
            outdoor_excess / outdoor_workers * 100_000
        ),
        "indoor_per_100k": (
            indoor_excess / indoor_workers * 100_000
            if indoor_workers > 0 else 0.0
        ),
        "odds_ratio": OUTDOOR_ODDS_RATIO,
        "odds_ratio_ci": OUTDOOR_ODDS_RATIO_CI,
    }
