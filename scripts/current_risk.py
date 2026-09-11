"""
Mortality risk for all five categories, at today's actual conditions.

The five are two independent axes, never added together:
  AGE        children / adults / elderly   - same exposure, different bodies
  OCCUPATION outdoor / indoor workers      - same bodies, different exposure

Run: python scripts/current_risk.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.weather.forecast_cache import get_cached_or_compute  # noqa: E402
from src.weather.climatology import Climatology  # noqa: E402
from src.mortality.heat_burden import HeatBurdenEngine  # noqa: E402

LINE = "=" * 76

weather, wards, city, records = get_cached_or_compute(forecast_days=5)
climatology = Climatology()
engine = HeatBurdenEngine()

today = records[0]
hottest = wards.sort_values("peak_utci_c", ascending=False).iloc[0]

print(LINE)
print("  CURRENT CONDITIONS")
print(LINE)
print("  date                     %s" % today["date"])
print("  city thermal index       %.1f C  (UTCI)" % today["utci_c"])
print("  normal for this date     %.1f C" % climatology.normal_for(
    today["date"])["utci_normal"])
print("  anomaly                  %+.1f C" % (
    today["utci_c"] - climatology.normal_for(today["date"])["utci_normal"]))
print("  hottest ward             %s at %.1f C"
      % (hottest["ward_name"], hottest["peak_utci_c"]))
print("  excess heat factor       %.1f" % today["ehf"])
print("  is this an event?        %s" % (
    "YES" if today["ehf"] > 0 else "NO - within the seasonal norm"))


def show(burden, label):
    indirect = burden["indirect_all_cause"]
    occ = indirect["by_occupation"]

    print()
    print("  %s" % label)
    print("  %-22s %12s %14s %12s"
          % ("category", "population", "excess deaths", "per 100,000"))
    print("  " + "-" * 62)

    for band in ("children", "adults", "elderly"):
        v = indirect["by_age"][band]
        print("  %-22s %12d %14.2f %12.4f"
              % (v["label"], v["population"], v["excess_deaths"],
                 v["excess_per_100k"]))

    if occ:
        print("  %-22s %12d %14.2f %12.4f"
              % ("Outdoor workers", occ["outdoor_workers"],
                 occ["outdoor_excess_deaths"], occ["outdoor_per_100k"]))
        print("  %-22s %12d %14.2f %12.4f"
              % ("Indoor workers", occ["indoor_workers"],
                 occ["indoor_excess_deaths"], occ["indoor_per_100k"]))
    else:
        print("  %-22s %12s %14.2f %12.4f"
              % ("Outdoor workers", "-", 0.0, 0.0))
        print("  %-22s %12s %14.2f %12.4f"
              % ("Indoor workers", "-", 0.0, 0.0))

    print("  " + "-" * 62)
    print("  %-22s %12s %14.2f"
          % ("citywide total", "", indirect["total"]))
    print("     the two axes describe the SAME people from different")
    print("     angles - workers are already inside the adult band above,")
    print("     so these two blocks must never be added together.")


burden = engine.daily_burden(
    utci_c=today["utci_c"],
    utci_normal_c=climatology.normal_for(today["date"])["utci_normal"],
    ehf=today["ehf"],
    night_temp_c=today.get("night_temp_c"),
    night_normal_c=climatology.night_normal_for(today["date"]),
)

print()
print(LINE)
print("  MORTALITY RISK - ALL FIVE CATEGORIES, TODAY")
print(LINE)
show(burden, "as of %s" % today["date"])

if today["ehf"] <= 0:
    print()
    print(LINE)
    print("  WHY EVERY FIGURE IS ZERO")
    print(LINE)
    print("  %.1f C is hot, but it is NORMAL for mid-September here."
          % today["utci_c"])
    print("  The model reports deaths caused by heat ABOVE the local")
    print("  seasonal norm. Today there is none, so the answer is zero.")
    print()
    print("  The same temperature in a cooler month WOULD be an event,")
    print("  because nobody is acclimatised to it yet:")

    # Same thermal index, but placed in March, when it is far above normal.
    march = "2026-03-15"
    march_normal = climatology.normal_for(march)["utci_normal"]
    counterfactual = engine.daily_burden(
        utci_c=today["utci_c"],
        utci_normal_c=march_normal,
        ehf=8.0,   # it would comfortably clear the event test
        night_temp_c=today.get("night_temp_c"),
        night_normal_c=climatology.night_normal_for(march),
    )
    print("     normal for 15 March is %.1f C, so %.1f C would be %+.1f C"
          % (march_normal, today["utci_c"], today["utci_c"] - march_normal))
    show(counterfactual, "the SAME %.1f C, but on 15 March" % today["utci_c"])
