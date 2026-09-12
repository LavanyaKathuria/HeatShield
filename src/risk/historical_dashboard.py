"""City-level historical weather through the shared live risk computation."""
import json
from functools import lru_cache
from copy import deepcopy
import pandas as pd
from src.weather.climatology import Climatology, compute_ehf_series
from src.weather.heat_stress import calculate_heat_stress, _utci_stress_category
from src.weather.weather_pipeline import evaluate_weather

METADATA = dict(source='may_2024', is_replay=True, start_date='2024-05-21', end_date='2024-05-25',
                peak_date='2024-05-23', weather_scope='citywide_applied_to_current_wards',
                mortality_kind='model_estimate', selection='highest_utci_in_1995_2024_archive')


@lru_cache(maxsize=1)
def _compute():
    climatology = Climatology()
    history = climatology.history.sort_values('date').reset_index(drop=True)
    ehf = compute_ehf_series(history.utci_c.to_numpy(), climatology.significance_series(history.date))
    by_date = dict(zip(history.date.dt.strftime('%Y-%m-%d'), ehf))
    selected = history[(history.date >= pd.Timestamp(METADATA['start_date'])) & (history.date <= pd.Timestamp(METADATA['end_date']))]
    if len(selected) != 5:
        raise ValueError('Incomplete historical event archive')
    with open('data/raw/wards/wards_ahmedabad.geojson', encoding='utf-8') as handle:
        features = json.load(handle)['features']
    wards = {str(f['properties']['sourcewardcode']): f['properties']['sourcewardname'] for f in features}
    rows = []
    for _, row in selected.iterrows():
        stress = calculate_heat_stress(row.temp, row.humidity, row.wind, row.radiation)
        stress.update(utci_c=float(row.utci_c), utci_stress_category=_utci_stress_category(row.utci_c))
        for ward_id, ward_name in wards.items():
            rows.append(dict(ward_id=ward_id, ward_name=ward_name, date=row.date.strftime('%Y-%m-%d'),
                tmax=row.tmax, tmin=row.tmin, night_temp_c=row.night_temp,
                afternoon_temp_c=row.temp, afternoon_humidity_pct=row.humidity,
                afternoon_wind_ms=row.wind, afternoon_solar_wm2=row.radiation, **stress))
    result = evaluate_weather(pd.DataFrame(rows), climatology, by_date)
    result[0]['is_replay'] = True
    result[2]['is_replay'] = True
    return result


def get_historical_dashboard():
    return deepcopy(_compute())


def historical_records():
    frame, *_ = get_historical_dashboard()
    return frame.astype(object).where(frame.notna(), None).to_dict('records')
