from .baseline import calculate_baseline_daily_deaths


class MortalityRuleEngine:
    """
    Literature-based heat mortality rule engine for Ahmedabad.

    This is a decision-support prototype, not a clinically
    validated mortality prediction model.
    """

    TMAX_THRESHOLD = 42.0
    TMIN_THRESHOLD = 28.0

    # Gujarat proxy mortality rate
    BASELINE_DEATH_RATE_PER_1000 = 5.6

    def __init__(self, population):
        self.population = population

    def calculate_baseline_daily_deaths(self):
        return calculate_baseline_daily_deaths(
            population=self.population,
            annual_death_rate_per_1000=self.BASELINE_DEATH_RATE_PER_1000
        )

    def calculate_relative_risk(
        self,
        tmax,
        tmin,
        previous_tmax=None,
        previous_tmin=None,
        two_days_ago_tmax=None,
        two_days_ago_tmin=None
    ):
        risk_percent = 0.0

        # Same-day effect
        if tmax >= self.TMAX_THRESHOLD:
            risk_percent += 9.56 * (
                tmax - self.TMAX_THRESHOLD
            )

        if tmin >= self.TMIN_THRESHOLD:
            risk_percent += 9.82 * (
                tmin - self.TMIN_THRESHOLD
            )

        # Lag 1-2 effect
        # Only calculate when both previous days are available.
        if (
            previous_tmax is not None
            and two_days_ago_tmax is not None
        ):
            avg_previous_tmax = (
                previous_tmax + two_days_ago_tmax
            ) / 2

            if avg_previous_tmax >= self.TMAX_THRESHOLD:
                risk_percent += 3.40 * (
                    avg_previous_tmax - self.TMAX_THRESHOLD
                )

        if (
            previous_tmin is not None
            and two_days_ago_tmin is not None
        ):
            avg_previous_tmin = (
                previous_tmin + two_days_ago_tmin
            ) / 2

            if avg_previous_tmin >= self.TMIN_THRESHOLD:
                risk_percent += 2.74 * (
                    avg_previous_tmin - self.TMIN_THRESHOLD
                )

        relative_risk = 1 + (
            risk_percent / 100
        )

        return relative_risk

    def calculate_excess_deaths(
        self,
        tmax,
        tmin,
        previous_tmax=None,
        previous_tmin=None,
        two_days_ago_tmax=None,
        two_days_ago_tmin=None
    ):
        baseline_deaths = (
            self.calculate_baseline_daily_deaths()
        )

        relative_risk = self.calculate_relative_risk(
            tmax=tmax,
            tmin=tmin,
            previous_tmax=previous_tmax,
            previous_tmin=previous_tmin,
            two_days_ago_tmax=two_days_ago_tmax,
            two_days_ago_tmin=two_days_ago_tmin
        )

        excess_deaths = (
            baseline_deaths * (relative_risk - 1)
        )

        return {
            "baseline_daily_deaths": baseline_deaths,
            "relative_risk": relative_risk,
            "risk_increase_percent": (
                relative_risk - 1
            ) * 100,
            "estimated_excess_deaths": excess_deaths
        }

    def calculate_heatwave_excess_deaths(
        self,
        weather_data
    ):
        daily_results = []

        for day in weather_data:

            result = self.calculate_excess_deaths(
                tmax=day["tmax"],
                tmin=day["tmin"],
                previous_tmax=day.get("previous_tmax"),
                previous_tmin=day.get("previous_tmin"),
                two_days_ago_tmax=day.get("two_days_ago_tmax"),
                two_days_ago_tmin=day.get("two_days_ago_tmin")
            )

            daily_results.append({
                "date": day.get("date"),
                "tmax": day["tmax"],
                "tmin": day["tmin"],
                **result
            })

        total_excess_deaths = sum(
            result["estimated_excess_deaths"]
            for result in daily_results
        )

        return {
            "heatwave_duration_days": len(weather_data),
            "daily_results": daily_results,
            "total_excess_deaths": total_excess_deaths
        }