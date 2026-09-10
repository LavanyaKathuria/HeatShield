# src/mortality/baseline.py


def calculate_baseline_daily_deaths(
    population,
    annual_death_rate_per_1000
):
    """
    Estimate average daily deaths from population and
    annual crude death rate.

    Parameters
    ----------
    population : int or float
        Population of the target area.

    annual_death_rate_per_1000 : float
        Annual crude death rate per 1,000 population.

    Returns
    -------
    float
        Estimated baseline deaths per day.
    """

    annual_deaths = (
        population
        * annual_death_rate_per_1000
        / 1000
    )

    return annual_deaths / 365