# Data sources behind the mortality model

Every numeric constant in `src/mortality/dose_response.py` traces back to one of the
sources below. PDFs/images live in `research/papers/` (gitignored — large binaries),
this file is the durable record of what was pulled from each one.

## 1. Sharma et al. 2024, *Urban Climate* 54:101832 — PRIMARY BACKBONE
"Characterizing the effects of extreme heat events on all-cause mortality: A case
study in Ahmedabad city of India, 2002-2018." DLNM, 21-day cumulative lag, 684,142
deaths, gender-stratified. `research/papers/sharma_2024_urban_climate_published.pdf`

- Minimum Mortality Temperature (MMT): **26°C** — the real reference point for "no
  excess heat risk," not an arbitrary cutoff.
- Full real dose-response curve (Table 3, cumulative RR at 21-day lag):

  | Tmax (°C) | All-sex RR | Male RR | Female RR |
  |---|---|---|---|
  | 38.0 (P85) | 1.13 | 1.10 | 1.18 |
  | 38.9 (P90) | 1.19 | 1.15 | 1.26 |
  | 39.5 (P93) | 1.25 | 1.20 | 1.33 |
  | 40.0 (P95) | 1.30 | 1.25 | 1.40 |
  | 40.7 (P97) | 1.40 | 1.33 | 1.51 |
  | 41.0 | 1.45 | 1.37 | 1.57 |
  | 41.8 (P99) | 1.61 | 1.52 | 1.75 |
  | 42.3 (P99.5) | 1.74 | 1.64 | 1.89 |
  | 45.0 | 3.08 | 3.03 | 3.11 |

- Attributable fraction: Tmax≥38°C (P85) accounts for **3.58%** of all deaths;
  the official ≥40°C alert threshold only captures **1.96%** — most of the real
  burden happens below the alert line.
- Gender: females at higher RR than males at every threshold (opposite direction
  from Guin et al.'s heatstroke-specific finding below — see note in dose_response.py).
- Caveat: 2002-2018 blends pre- and post-2013 HAP years into one curve (same
  regime-blending caveat as Wei et al. below).

## 2. Hess et al. 2018, *J. Environ. Public Health* 2018:7973519
"Building Resilience to Climate Change: Pilot Evaluation of the Impact of India's
First Heat Action Plan on All-Cause Mortality." `research/papers/hess_2018_hap_pre_post_evaluation.pdf`

- Pre-HAP (2007-2010) vs post-HAP (2014-2015) RR at 47°C (ref. 40°C): **2.34 → 1.25**.
- Figure 3 (read directly from the rendered PDF page): both curves flat ~1.0 from
  30-42°C; pre-HAP climbs convexly above 42°C; post-HAP stays flat until ~44-45°C.
  **The post-HAP line is dashed above ~44-45°C in the paper itself** — i.e. even
  Hess et al.'s own post-HAP RR=1.25 at 47°C is a model extrapolation beyond data
  they actually observed (Ahmedabad didn't get that hot in 2014-2015).
- 1,190 annualized deaths avoided post-HAP (95% CI 162-2,218).
- Used here as a cross-check on the Sharma et al. curve, not as the primary curve
  (Sharma et al. has 9 real points and a real MMT; Hess et al. has 2 anchor points).

## 3. Dutta et al. 2022, *Aerosol and Air Quality Research* letter — VALIDATION ANCHORS
"A Successful Heat Wave Prevention in Ahmedabad Calls for Segregated Health Record."
`research/papers/dutta_2022_segregated_health_record_letter.pdf`

Real, year-by-year Ahmedabad heatstroke case (death) counts — **the multi-year
validation set used in `tests/test_dose_response.py`**:

| Year | Cases (Deaths) | Note |
|---|---|---|
| 2010 | 274 (65) | pre-HAP, the catastrophic event |
| 2014 | 57 (11) | post-HAP |
| 2015 | 23 (8) | post-HAP, mild year |
| 2016 | 99 (15) | post-HAP, includes the all-time record 48.0°C day (IMD, May 20) |
| 2017 | 33 (2) | post-HAP |
| 2018 | 26 (3) | post-HAP |

## 4. Azhar et al. 2014, PLOS ONE 9(3):e91831
"Heat-Related Mortality in India: Excess All-Cause Mortality Associated with the
2010 Ahmedabad Heat Wave." Source of the well-known May 2010 numbers: 4,462 total
deaths, 1,344 excess (+43.1%), acute-week (May 19-25) RR 1.76-2.12.

## 5. Wei et al. 2021, PMC8169607
"Assessing mortality risk attributable to high ambient temperatures in Ahmedabad,
1987-2017." Source of the *original* linear Tmax/Tmin coefficients this project
started with (9.56%/9.82% lag0, 3.40%/2.74% lag1-2, thresholds 42°C/28°C) — now
superseded by the Sharma et al. curve above, which is non-linear (real J-shape,
not a linear approximation) and has 9 real points instead of one linear slope.
Also: 65+ = 35.5% of all 337,086 deaths studied (all-cause baseline age share,
not a heat-specific age RR); South municipal zone flagged most heat-vulnerable
(qualitative, no numeric zone RR given).

## 6. Guin, Bhan & Sethi 2025, *Temperature* 12(2):179-199 — AGE/GENDER PROXY FOR OCCUPATION
"Mortality due to heatstroke and exposure to cold: Evidence from India." NCRB+IMD
panel, 24 states, 2001-2019. National (not Ahmedabad-specific) heatstroke-classified
death age/gender breakdown:

- Age: <30 ≈13%, **30-59 ≈59%**, 60+ ≈28% of heatstroke deaths.
- Gender: ~79% male.
- Explicitly attributed by the authors to outdoor livelihood/occupational exposure
  ("as more men compared to women in India work outdoors... men may be more
  vulnerable to heat due to their engagement in livelihood-generating activities").
- This is the closest real, citable substitute for occupation data — no source
  anywhere gives a direct indoor/outdoor mortality coefficient. Used only as a
  labeled proxy, never presented as a direct occupational measurement.

## 7. Census of India 2011 — demographic denominators
`data/raw/census/DDW_PCA2407_2011_ward_pca.xlsx` (Primary Census Abstract, Ahmedabad
district code 474) and `DDW_2400_C14_age_data.xls` (C-14 age-by-5-year-band table).

- Ahmedabad Municipal Corporation total population: 5,577,940 (ties out exactly to
  Azhar et al.'s cited 5.571M and to the existing `ahmedabad_census_2011.csv`).
- 57 correctly-cleaned wards (63 raw rows include overlapping "M Corp + Outgrowth"
  entries that get filtered) — does NOT match the current 48-ward operational
  geometry. No verified crosswalk exists; city-wide constants are used instead of
  fake ward-level precision.
- No age-band data beyond 0-6 exists at ward level (confirmed directly from the
  primary PCA file) — elderly ward-level data is not obtainable from this source.
- Ahmedabad district **urban** age pyramid (proxy for the city), used to compute
  per-capita relative vulnerability (mortality share ÷ population share):
  - 60+: 480,980 of 6,063,047 urban population = **7.9%**
  - 65+: 300,889 = **5.0%**
  - 30-59: 2,284,176 = **37.7%**
  - Combined with #5/#6 above: elderly ~4.5x over-represented in all-cause heat
    deaths relative to population share; working-age (30-59) ~1.6x over-represented
    in heatstroke-classified deaths.

## 8. IMD city extreme records
https://city.imd.gov.in/citywx/extreme/MAR/ahmedabad2.htm — all-time record Tmax
for Ahmedabad: **48.0°C, May 20, 2016** (higher than 2010's 46.8°C).

## 9. Venugopal, Shanmugam & Kamalakkannan 2021, *Environmental Research Letters* 16(8) — INDOOR VS OUTDOOR JUGAAD
"Heat-health vulnerabilities in the climate change context - comparing risk
profiles between indoor and outdoor workers in developing country settings."
Tamil Nadu, India (not Ahmedabad - same country, comparable climate/informal-
labour context, closest real study that directly compares the two groups).

- N=2,104: 1,053 Outdoor Unorganized Workers (agriculture, construction,
  brick-making, salt pans), 1,051 Indoor Organized Workers (kitchens,
  garments, steel & foundry).
- Any heat-illness symptoms: outdoor 90.3% vs indoor 78.3%.
- **Adjusted odds ratio, outdoor vs indoor, heat-illness symptoms: 2.1
  (95% CI 1.60-2.77)** - adjusted for workload, literacy, age.
- Productivity loss AOR 11.4 (7.39-17.6); reduced kidney function OR 1.4
  (1.10-1.84).
- Measured WBGT was actually slightly *higher* indoors (29.8 vs 29.1°C,
  poor ventilation in steel/foundry) - the excess outdoor risk is about
  workload intensity and protection/awareness gaps, not raw heat exposure.
- Used as `occupational_exposure_multiplier` in
  `src/mortality/exposure_setting.py` - an advisory-targeting modifier,
  never blended into the core excess-death number (no Ahmedabad-specific
  population split between outdoor/indoor workers exists to weight it by).

## 10. Ranadive et al. 2021, PMC8203017 — AHMEDABAD-SPECIFIC EMS DATA
"Climate Change Adaptation: Prehospital Data Facilitate the Detection of
Acute Heat Illness in India." Ahmedabad, GVK-EMRI "108" ambulance service,
480 patients, April-June 2016 (post-HAP).

- Pickup location: residence 91.5%, worksite 3.5%, outdoor public space
  2.9%, indoor public space 0.8%.
- 83.96% of patients reported an *indoor* occupation.
- On-scene air conditioning was protective: OR 0.29 (95% CI 0.10-0.85).
- Logger heat index >=49°C: OR 2.66 (1.13-6.25) for illness severity.
- This is a different population/pathway than #9 above: Venugopal studies
  active workers on the job (outdoor work is worse there); this is who
  actually calls emergency services in Ahmedabad, which skews toward
  home-bound people without cooling access. Both are real and kept
  separate rather than forced into one number - see `exposure_setting.py`.

## 11. de Bont et al. 2024, *Environment International* — context only
10-city India multi-city study (PMC11790314), 2008-2019. National average +14.7%
mortality for 2-consecutive-day 97th-percentile events. Confirms (again) no
age/gender/occupation data is available in Indian mortality registration generally.
Not used as a numeric input — context/consistency check only.
