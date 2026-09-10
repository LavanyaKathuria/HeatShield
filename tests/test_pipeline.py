from src.mortality.mortality_engine import MortalityRuleEngine
from src.vulnerability.ward_risk import WardRiskModel
from src.weather.weather_pipeline import get_weather_mortality_risk

def test_mortality_to_ward_pipeline():

    # Ahmedabad population used by our current prototype
    population = 9_432_449

    # Create mortality engine
    mortality = MortalityRuleEngine(population)

    # Example hot day
    mortality_result = mortality.calculate_excess_deaths(
        tmax=43,
        tmin=29,
        previous_tmax=42,
        previous_tmin=28,
        two_days_ago_tmax=43,
        two_days_ago_tmin=29
    )

    heat_exposure = mortality_result["risk_increase_percent"]

    # Create ward risk model
    wards = WardRiskModel()

    wards.predict_clusters()
    result = wards.calculate_priority_scores(
        heat_exposure=heat_exposure
    )

    ranked = wards.get_ranked_wards()

    print("\nTop priority wards:")
    print(
        ranked[
            [
                "ward_id",
                "ward_name",
                "final_priority_score",
                "final_priority_category"
            ]
        ].head(10).to_string(index=False)
    )

    assert len(result) == 48
    assert heat_exposure > 0
    assert result["final_priority_score"].notna().all()

def test_weather_mortality_pipeline():

    results = get_weather_mortality_risk(
        forecast_days=3
    )

    assert len(results) == 3

    for result in results:

        assert "tmax" in result
        assert "tmin" in result

        assert "previous_tmax" in result
        assert "previous_tmin" in result

        assert "two_days_ago_tmax" in result
        assert "two_days_ago_tmin" in result

        assert "risk_increase_percent" in result
        assert "estimated_excess_deaths" in result