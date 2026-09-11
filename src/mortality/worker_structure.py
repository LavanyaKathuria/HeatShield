"""
Occupational exposure denominators, assembled from the Census Primary
Census Abstract.

WHY THIS IS ASSEMBLED RATHER THAN LOOKED UP
-------------------------------------------
No source gives "outdoor workers in this city". The census gives four
worker categories, only two of which are unambiguously outdoor, and in an
urban district those two are tiny - the real outdoor workforce
(construction, transport, street vending, waste handling, delivery) is all
buried inside the residual "Other workers" category.

So the count is built in three pieces, and the seam is left visible:

    outdoor = cultivators          (census, exact, outdoor by definition)
            + agricultural labour  (census, exact, outdoor by definition)
            + other workers x f    (f from national labour-survey
                                    industry shares - the soft part)

Everything except `f` is a counted number from a real table. `f` is
declared here as a single named constant rather than being smuggled into
the middle of a formula, so it can be argued with, replaced, or
sensitivity-tested on its own.

Household-industry workers are treated as indoor.
"""

import pandas as pd

PCA_FILE = "data/raw/census/DDW_PCA2407_2011_ward_pca.xlsx"

DISTRICT = "Ahmadabad"
RESIDENCE = "Urban"

# Share of "Other workers" in an urban Indian district whose work is
# substantially outdoors - construction, transport and storage, street
# vending, waste handling, delivery and other open-air informal work.
# Derived from national labour-survey industry shares, not from the
# census itself. THIS IS THE SOFT NUMBER IN THIS MODULE. It moves the
# outdoor headcount roughly proportionally, so treat any outdoor-worker
# figure as accurate to about a factor of 1.5, not to three digits.
OUTDOOR_SHARE_OF_OTHER_WORKERS = 0.27

# Outdoor vs indoor workers, adjusted odds ratio for heat-illness
# symptoms - Venugopal et al. 2021, N=2,104, AOR 2.1 (95% CI 1.60-2.77).
OUTDOOR_ODDS_RATIO = 2.1
OUTDOOR_ODDS_RATIO_CI = (1.60, 2.77)


def _district_row(path=PCA_FILE):

    raw = pd.read_excel(path, header=None)
    header = raw.iloc[0].tolist()
    body = raw.iloc[1:].copy()
    body.columns = header

    match = body[
        (body["Level"] == "DISTRICT")
        & (body["Name"].astype(str).str.strip() == DISTRICT)
        & (body["TRU"] == RESIDENCE)
    ]

    if match.empty:
        raise ValueError(
            f"no {RESIDENCE} row for {DISTRICT} in {path}"
        )

    return match.iloc[0]


def worker_breakdown(path=PCA_FILE):
    """
    Counted worker categories, main plus marginal, for the urban district.
    """

    row = _district_row(path)

    def total(prefix):
        return int(row[f"MAIN{prefix}"]) + int(row[f"MARG{prefix}"])

    cultivators = total("_CL_P")
    agricultural = total("_AL_P")
    household_industry = total("_HH_P")
    other = total("_OT_P")

    all_workers = int(row["TOT_WORK_P"])
    population = int(row["TOT_P"])

    definitely_outdoor = cultivators + agricultural
    estimated_outdoor = definitely_outdoor + round(
        other * OUTDOOR_SHARE_OF_OTHER_WORKERS
    )

    return {
        "population": population,
        "all_workers": all_workers,
        "worker_share_of_population": all_workers / population,
        "cultivators": cultivators,
        "agricultural_labourers": agricultural,
        "household_industry": household_industry,
        "other_workers": other,
        "definitely_outdoor": definitely_outdoor,
        "estimated_outdoor_workers": estimated_outdoor,
        "estimated_indoor_workers": all_workers - estimated_outdoor,
        "outdoor_share_of_workers": estimated_outdoor / all_workers,
        "outdoor_share_of_population": estimated_outdoor / population,
    }


def scaled_outdoor_workers(total_population, path=PCA_FILE):
    """
    Outdoor worker count scaled from the census population to a current
    population total, holding the occupational structure constant.
    """

    breakdown = worker_breakdown(path)

    return round(
        total_population * breakdown["outdoor_share_of_population"]
    )


def outdoor_indoor_split(excess_in_adults, outdoor_fraction_of_adults):
    """
    Divide an adult-band burden between outdoor and indoor workers using
    the measured odds ratio.

    Solving for the two rates that both preserve the adult total and
    respect the odds ratio, rather than simply multiplying the adult
    figure by 2.1 - which would invent burden that does not exist.
    """

    f = outdoor_fraction_of_adults
    ratio = OUTDOOR_ODDS_RATIO

    # indoor_rate x ((1 - f) + f x ratio) = adult_rate
    denominator = (1 - f) + f * ratio

    indoor_share = (1 - f) / denominator
    outdoor_share = (f * ratio) / denominator

    return {
        "outdoor_excess": excess_in_adults * outdoor_share,
        "indoor_excess": excess_in_adults * indoor_share,
        "odds_ratio": ratio,
        "odds_ratio_ci": OUTDOOR_ODDS_RATIO_CI,
    }


if __name__ == "__main__":

    b = worker_breakdown()

    print("Census urban worker structure")
    print("  population                %10d" % b["population"])
    print("  all workers               %10d  (%.1f%% of population)"
          % (b["all_workers"], 100 * b["worker_share_of_population"]))
    print("  cultivators               %10d   counted, outdoor"
          % b["cultivators"])
    print("  agricultural labourers    %10d   counted, outdoor"
          % b["agricultural_labourers"])
    print("  household industry        %10d   counted, indoor"
          % b["household_industry"])
    print("  other workers             %10d   mixed - the problem category"
          % b["other_workers"])
    print()
    print("  definitely outdoor        %10d  (%.1f%% of workers)"
          % (b["definitely_outdoor"],
             100 * b["definitely_outdoor"] / b["all_workers"]))
    print("  estimated outdoor         %10d  (%.1f%% of workers)"
          % (b["estimated_outdoor_workers"],
             100 * b["outdoor_share_of_workers"]))
