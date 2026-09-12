import json
import pytest
from src.risk.historical_dashboard import get_historical_dashboard, METADATA
from src.weather.climatology import Climatology


def test_replay_matches_archive_peak_and_citywide_scope():
    frame, wards, burden, records = get_historical_dashboard()
    history = Climatology().history
    peak = history.loc[history.utci_c.idxmax()]
    assert peak.date.strftime('%Y-%m-%d') == METADATA['peak_date']
    assert peak.utci_c == 52.3
    assert len(frame) == 48 * 5
    assert frame.groupby('date').utci_c.nunique().eq(1).all()
    assert frame.utci_c.max() == peak.utci_c
    assert burden['heatwave_detected'] and burden['is_replay']
    assert burden['total_excess_deaths'] == pytest.approx(sum(d['excess_deaths'] for d in burden['daily']), abs=0.2)
    assert 250 < burden['total_excess_deaths'] < 350
    # Callers cannot pollute the cached historical dataset.
    frame['utci_c'] = 0
    assert get_historical_dashboard()[0].utci_c.max() == 52.3


def test_replay_read_endpoints_never_fetch_live_or_send(monkeypatch):
    from src import api
    from src.alerts import routes
    def forbidden(*args, **kwargs):
        raise AssertionError('Replay reads must not fetch live weather or send')
    monkeypatch.setattr(api, 'get_cached_or_compute', forbidden)
    monkeypatch.setattr(routes, 'send_whatsapp', forbidden)
    for handler in (api.ward_priority, api.ward_forecast_timeline, api.heat_event):
        result = handler(forecast_days=3, source='may_2024')
        assert result['forecast_days'] == 5
        assert result['metadata'] == METADATA
        json.dumps(result, allow_nan=False)
        if 'citywide' in result:
            assert result['citywide']['forecast_generated_at'] is None
