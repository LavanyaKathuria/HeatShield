# HeatShield

## Setup

You need **Python 3.11+** and **Node 22.12+** (the frontend uses Vite 8).

### 1. Backend

```bash
pip install -r requirements.txt
python -m uvicorn src.api:app --port 8000
```

Open http://127.0.0.1:8000/docs to see every endpoint.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env        # then fill in the two Supabase values
npm run dev
```

Open http://localhost:5173.

The frontend proxies `/api` → `http://127.0.0.1:8000`, so **the backend must be
running** or the map will be empty.

### 3. Check it works

```bash
python scripts/check_api.py        # backend, with the server running
python scripts/current_risk.py     # today's risk for all five categories
python -m pytest tests -q
```

### Environment keys

The weather API is free and keyless. WhatsApp alerts also need backend Supabase
and Twilio configuration; see [WhatsApp setup](docs/WHATSAPP_ALERTS.md).

Put these in `frontend/.env` (copy from `frontend/.env.example`):

| key | what it is |
|---|---|
| `VITE_SUPABASE_URL` | your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon** key — safe to be public; it ships in the browser bundle and is protected by row-level security |
| `VITE_API_BASE_URL` | *optional*, leave unset in dev (the proxy handles it) |

> Keep the Supabase **service-role** key in backend secret storage or the
> gitignored root `.env` only. Never put it in frontend variables or tracked files.
> It bypasses row-level security entirely.
>
> `.env` files are gitignored. Share keys through a password manager, not email
> or chat — email keeps a copy on every server and device it touches, forever.

### Common problems

**Map is empty / "data temporarily unavailable"** — the backend isn't running,
or something else is holding port 8000. Check with:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

A stale server silently keeps the port and serves old code, which looks exactly
like a frontend bug. Kill it and restart.

**First request is slow** — the pipeline computes 48 wards of thermal stress and
risk, then caches it for 3 hours. Later requests are instant.

---

## How it works

Six steps. Each answers one question and feeds the next.

### 1. Weather in

Open-Meteo forecast for the centroid of each of the **48 AMC wards**:
temperature, humidity, wind and solar radiation, hourly, 5 days ahead.

Only the **12:00–15:00** window is used. A 24-hour average would blend the
dangerous afternoon with a cool 4am and hide the hours that actually kill.

### 2. What the body feels

Those four numbers become three published indices:

| index | uses | what it tells you |
|---|---|---|
| Heat Index | temp + humidity | what it "feels like" |
| WBGT | temp + humidity | the occupational standard for work/rest limits |
| **UTCI** | **all four** | **the main index** — everything downstream uses it |

40°C at 20% humidity and 40°C at 70% are the same temperature and very
different dangers. This is the step that knows the difference.

### 3. Is this unusual *here*?

The most important step, and the one that's easy to get wrong.

42°C in May is a normal Tuesday in Ahmedabad. 42°C in September is an
emergency, because nobody's body is ready for it. So every day is compared
against **what is normal for that place on that calendar date**, using a
30-year record (10,958 real days, 1995–2024) built into `data/cleaned/`.

The "normal" is the average of the **15 years before** that date — people are
acclimatised to the climate they have recently lived through, not to a 30-year
average that a warming trend has pulled below present conditions.

### 4. Is it an *event*?

Anomaly alone isn't enough. We use the **Excess Heat Factor**, which asks two
questions at once:

- **Is it hot by this city's standards, for this date?**
- **Is it hot compared to the last 30 days?** ← the crucial one

The second is why three months at 34°C is *not* a heatwave. After weeks of
heat the body has adapted, so the same temperature stops being an emergency.
Heat kills on the way up, not on the plateau.

Result: about **12 event days a year**. Not 200.

### 5. How many people, and which people

```
excess deaths = baseline deaths × attributable fraction × susceptibility
```

**Baseline** — how many people die on a normal day anyway. From AMC's own death
registry: **2.19 deaths per 100,000 per day** (684,142 registered deaths,
2002–2018). Applied to the Census 2011 municipal population of 5,577,940, that
is **122 deaths a day**. This is the biggest number in the whole model, and
it has no weather in it — it's the denominator.

**Attributable fraction** — the share of those deaths caused by heat *above the
seasonal normal*, from a published dose-response curve for this city
(684,142 deaths, 21-day lag). Zero on an ordinary day, by construction.

**Susceptibility** — who it lands on. Two **independent** axes:

| axis | what it isolates |
|---|---|
| **Age** — children / adults / elderly | same place, same heat, different bodies |
| **Occupation** — outdoor / indoor workers | same bodies, different exposure |

They describe the *same people* from different angles. Workers are already
inside the adult band, so **the two axes are never added together**.

Elderly carry about **21× the adult risk per person**. That isn't assumed — it
is 10.4× from their baseline death rate (they are 5% of the population and
35.5% of all deaths) times 2.07× from heat susceptibility.

### 6. What comes out

Per ward, per day: thermal indices, the anomaly, the event severity, a risk
level per group, and the overall level that colours the map.

Citywide: excess deaths with a real confidence range.

---

## The rules this system follows

Learned the hard way; each one exists because breaking it caused a real bug.

**Compare to local normal, never to a fixed number.** An earlier version scored
every day against a fixed 26°C and reported deaths on 292 days a year.

**One question, one answer.** Every part must agree. We once showed "nobody is
at elevated risk" directly above "21 additional deaths" — two subsystems using
two different baselines.

**Silence is a valid output.** On most days nobody is at risk and the correct
answer is zero. A system uncomfortable saying nothing will invent something.

**Failures must be loud.** The event detector once crashed on *every single
run*, got swallowed by error handling, and quietly returned "no data" — which
the rest of the system read as "no heatwave". It never ran once, and nothing
said so.

**Never claim precision we don't have.** Mortality is reported **citywide
only**. Ward-level death records don't exist anywhere in India, so any
ward-level death count would be a city number divided by a formula.

**Every number must be traceable.** To a measurement, a published paper, or a
clearly labelled assumption. There are exactly three soft numbers left, each
named in one place: `OUTDOOR_SHARE_OF_OTHER_WORKERS`,
`CHILD_TO_ADULT_RATE_RATIO`, `ELDERLY_RELATIVE_SUSCEPTIBILITY`.

---

## API

| endpoint | what it gives you |
|---|---|
| `GET /ward-priority` | all 48 wards ranked, plus the citywide summary |
| `GET /ward-forecast-timeline` | every ward × every day (240 rows) — drives the 5-day scrubber |
| `GET /heat-event` | is a heat event forecast, how severe, which wards |
| `GET /risk-levels` | **every threshold, published** — so the system can be audited |

All accept `?forecast_days=3..5`.

---

## Project layout

```
src/
  api.py                    FastAPI endpoints
  weather/
    ward_weather.py         fetches the 48-ward forecast
    heat_stress.py          UTCI / WBGT / Heat Index  (pure physics)
    climatology.py          30-year normals + Excess Heat Factor
    live_ehf.py             stitches recent history onto the forecast
    weather_pipeline.py     runs all of it, ward by ward
    forecast_cache.py       3-hour cache of the finished result
  mortality/
    age_structure.py        population, death rates  <- the two key numbers
    dose_response.py        the published heat-mortality curve
    heat_burden.py          the engine: weather -> deaths by group
    risk_axes.py            the two axes, kept independent
    worker_structure.py     outdoor/indoor worker counts from the census
  risk/
    levels.py               thresholds: which group is at which level
    scenario.py             replays real past heatwaves, for testing

frontend/src/               React + MapLibre dashboard, EN / HI / GU
scripts/                    build climatology, refresh cache, smoke tests
tests/                      20 tests
handover/                   original alerting archive
src/alerts/                 active WhatsApp targeting, rendering and delivery
research/SOURCES.md         every number, and where it came from
```

---

## WhatsApp alerts

English, Hindi and Gujarati WhatsApp alerts are connected to the existing risk
engine. Both dashboards use saved account contact and language preferences and
provide personalized forecast advisories and message history. A scheduled worker handles
delivery, event deduplication and escalation using a persistent ledger.

See [setup, previews, templates and scheduling](docs/WHATSAPP_ALERTS.md).
The **Historical heatwave** navigation control replays 21–25 May 2024, opening
on the archive's highest-UTCI day, 23 May. It updates dashboard data and sends
eligible sandbox replay alerts for the signed-in account. Citywide mortality is
a model estimate; archived city weather is applied uniformly across current wards.
Historical previews run without credentials:

```bash
python scripts/dispatch_alerts.py --scenario may_2024 --language gu
```

The original `handover/` remains an archive. SMS and voice transport are still
pending; this implementation delivers WhatsApp text.

---

## Known limits

Stated plainly, because a judge will ask.

- **Ward-level mortality does not exist.** India registers deaths at city level
  at best. Ward figures would be a city number split by a formula.
- **The 2011 census wards (57) don't map to today's wards (48).** No published
  crosswalk exists, so ward demographics can't currently be attached to the map.
- **Population is Census 2011**, so death counts are conservative.
- **The curve extrapolates about one day a year**, past UTCI 50.4. Those are
  the deadliest days. The figure is kept rather than capped — capping would
  understate exactly the days that matter — but it is a lower bound and is
  flagged as `is_beyond_observed_range`.
- **Recorded heat deaths can't validate this.** Against six years of municipal
  records the rank correlation is ≈0. That series is driven by the Heat Action
  Plan and by what gets *classified* as a heat death, not by weather. We
  validate on **ordering** and on published excess-mortality studies instead.

## Validation

| check | result |
|---|---|
| May 2010 excess deaths | **1,449 modelled** vs 1,344 independently measured (+7.8%) |
| 2010's rank in 30 years | **1st** — correctly the worst |
| annual heat burden | **3.3%** of all deaths vs 3.58% published |
| 30% surge above 40°C | our curve gives **exactly +30%** |
| elderly death rate | model derives **57.1**/1,000; published rates weighted by our age structure give **56.5** |
| an ordinary day | **0 deaths, nobody named at risk** |
