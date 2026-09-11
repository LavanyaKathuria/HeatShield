# HeatShield

## Setup

You need **Python 3.11+** and **Node 18+**.

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
python -m pytest tests -q          # 20 tests
```

### Environment keys

Only the **frontend** needs keys. The backend needs none — the weather API is
free and keyless.

Put these in `frontend/.env` (copy from `frontend/.env.example`):

| key | what it is |
|---|---|
| `VITE_SUPABASE_URL` | your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon** key — safe to be public; it ships in the browser bundle and is protected by row-level security |
| `VITE_API_BASE_URL` | *optional*, leave unset in dev (the proxy handles it) |

> **Never** put the Supabase **service-role** key anywhere in this repo. It
> bypasses row-level security entirely. If it has ever been shared, rotate it.
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
handover/                   the alerting layer (see below)
research/SOURCES.md         every number, and where it came from
```

---

## The alerting system — for whoever builds it next

**Status: designed, written, tested, and deliberately lifted out.** Everything
in `handover/` was running end to end before being removed. It does not need
rewriting. It needs reconnecting.

### The goal, in one sentence

**Get the right advice to the right person, in their own language, early enough
to act on — including to people who cannot read.**

That last clause is the whole point. A dashboard reaches officials. SMS reaches
literate people with phones. Neither reaches the elderly woman living alone or
the construction worker who left school at eleven — and those are precisely the
people who die. If the system only ever produces a beautiful map, it has
failed at its actual job.

### When do we send an alert?

Three conditions. **All three** must be true:

**1. It's a heat event.** The Excess Heat Factor is positive — today is
genuinely unusual for this place and this date. Not merely hot. In this climate
"hot" is most of the year, and a warning that fires most of the year is not a
warning; it is noise that teaches people to ignore the next one.

**2. A group's threshold is crossed.** Each group is judged on the measure that
governs its own response — mortality is the wrong endpoint for most of them:

| group | measured on | why that measure |
|---|---|---|
| Elderly | excess deaths per 100,000 | the endpoint really is death, and it arrives for them first |
| Outdoor workers | WBGT | it's the occupational standard that sets work/rest cycles |
| Children | thermal stress index | the endpoint is safe outdoor activity, not mortality |
| General public | event severity | awareness during an unusual event |

**3. The recipient is in that group** — themselves, or through a family member
they've added.

So if only the elderly threshold is crossed, **only households containing an
older person** get the elderly advisory. A construction worker with no elderly
relatives gets the general notice, or silence. Everyone getting everything is
how a warning system becomes wallpaper.

This decision is **already built and running.** `src/risk/levels.py` computes a
level per group for every ward and every forecast day; `weather_pipeline` writes
it to `group_levels` on each row; the API returns it. What was removed is only
the part that turns that decision into a message and sends it.

Also already exposed: `work_rest_key` on every ward. That's standing
occupational guidance ("15 min work / 45 min rest"), produced **every day**,
event or not. Guidance is a fact about the conditions; an alert is a claim that
today is different. Don't conflate them — in this climate the work/rest advice
is warranted for much of the year, and if it went out as an *alert* it would
destroy the credibility of the real ones.

### Deduplication

One message per **ward + group + level** per event. A 5-day forecast must not
produce five near-identical messages. Re-send only when the event **escalates** —
that is the one repeat worth making.

### Channels, and why each exists

| channel | for whom | status |
|---|---|---|
| **Voice call** | anyone who may not read a written alert — **the whole point** | designed, not wired |
| WhatsApp | smartphone users | **working** (Twilio Sandbox) |
| SMS | feature-phone users | designed, needs DLT registration |
| Dashboard | officials, hospitals, schools | working |

### What's in `handover/`

| file | |
|---|---|
| `advisories.py` | which message applies to which audience at which level, plus lead-timed institutional checklists |
| `engine.py` | targeting — who receives what, and on which channel |
| `render.py` | keys + language → exact text per channel |
| `dispatch.py` | WhatsApp delivery via Twilio Sandbox, dry-run by default |
| `advisory-content/{en,hi,gu}.json` | **~160 keys × 3 languages** — the genuinely expensive part |

`handover/README.md` has the reconnection steps. Only two imports need fixing:
`src.alerts.triggers` → `src.risk.levels`, same function names.

### Things worth not relearning the hard way

- **Advisories must be specific.** "Stay hydrated" is not advice. "One glass
  every 30 minutes, even if you are not thirsty" is — and it carries the reason
  (after 65 the thirst signal weakens), because the reason is what makes people
  comply.
- **Devanagari and Gujarati cost 70 characters per SMS segment, not 160.**
  A message sized for Latin script silently triples in cost or gets truncated.
- **Voice scripts are written separately, never the SMS read aloud.** A
  listener cannot re-read a sentence. The scripts lead with the action, avoid
  lists, and repeat the key instruction at the end. "108" is spelled out in
  words so it is unambiguous over a phone line.
- **Pre-record the voice clips with a native speaker.** 12 scripts × 3
  languages = 36 files, recorded once. Gujarati text-to-speech isn't supported
  by the voices behind Twilio at all, and synthetic Hindi is hard for an
  elderly listener to parse.
- **Every test or replayed message must be labelled a drill**, in the
  recipient's own language, at the top. `dispatch.py` enforces this in code
  rather than leaving it to memory. A realistic emergency warning that isn't
  real is something people act on.
- **`dry_run` defaults to True.** Forgetting the flag gives you a preview, not
  a message.
- **The Twilio join code is a sandbox limitation, not a product step.** A real
  WhatsApp Business sender needs no join phrase.

### Demonstrating it when there's no heatwave

There usually isn't one on demo day, and inventing weather until the thresholds
trip proves nothing — any system can be made to alert on numbers chosen to make
it alert.

Instead, **replay a real event**. `src/risk/scenario.py` runs the actual
recorded May 2024 heatwave (the most intense in the 30-year record) through the
same engine, the same triggers, the same renderer. Only the weather source is
swapped. `may_2010` and `may_2016` are also available.

### Still missing

- SMS and voice transport (both payloads are already produced by `render.py`)
- the 36 voice recordings
- a delivery log — `engine.alert_fingerprint()` exists for deduplication, but
  nothing persists what actually went out

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
